package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"time"

	"github.com/ahenzinger/simplepir/pir"
)

const (
	logQ      = uint64(32)
	secParam  = uint64(1 << 10)
	recordLen = 32
	chunkBits = uint64(32)
	chunks    = 8
)

type Subdatabase struct {
	Color        int    `json:"color"`
	Records      int    `json:"records"`
	RecordBytes  int    `json:"record_bytes"`
	DatabaseFile string `json:"database_file"`
	QueryIndices []int  `json:"query_indices"`
}

type Manifest struct {
	Scheme       string        `json:"scheme"`
	Height       int           `json:"height"`
	Width        int           `json:"width"`
	ActiveNodes  int           `json:"active_nodes"`
	QuerySamples int           `json:"query_samples"`
	Subdatabases []Subdatabase `json:"subdatabases"`
}

type ChunkBackend struct {
	params       pir.Params
	db           *pir.Database
	shared       pir.State
	server       pir.State
	offline      pir.Msg
	expectedVals []uint64
	setupMS      float64
	offlineKB    float64
}

type ColorBackend struct {
	color    int
	records  int
	chunkDBs [chunks]*ChunkBackend
}

type Result struct {
	Scheme              string  `json:"scheme"`
	Height              int     `json:"height"`
	Width               int     `json:"width"`
	ActiveNodes         int     `json:"active_nodes"`
	QuerySamples        int     `json:"query_samples"`
	RecordBytes         int     `json:"record_bytes"`
	ChunkBits           int     `json:"chunk_bits"`
	ChunkedQueries      int     `json:"chunked_queries_per_color"`
	Colors              int     `json:"colors"`
	StoredRecordsPadded int     `json:"stored_records_with_padding"`
	SetupMS             float64 `json:"setup_ms"`
	ClientQueryMS        float64 `json:"client_query_ms"`
	ServerTotalMS        float64 `json:"server_total_ms"`
	ServerParallelMS     float64 `json:"server_parallel_ms"`
	ClientDecodeMS       float64 `json:"client_decode_ms"`
	OfflineKB           float64 `json:"offline_kb"`
	OnlineUploadKB      float64 `json:"online_upload_kb"`
	OnlineDownloadKB    float64 `json:"online_download_kb"`
	OnlineTotalKB       float64 `json:"online_total_kb"`
}

func msgKB(msg pir.Msg, p pir.Params) float64 {
	return float64(msg.Size()*p.Logq) / (8.0 * 1024.0)
}

func loadRecords(path string, records int, recordBytes int) ([]byte, error) {
	if recordBytes != recordLen {
		return nil, fmt.Errorf("expected %d-byte records, got %d", recordLen, recordBytes)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	expected := records * recordBytes
	if len(raw) != expected {
		return nil, fmt.Errorf("%s has %d bytes, expected %d", path, len(raw), expected)
	}
	return raw, nil
}

func chunkValues(raw []byte, records int, chunk int) []uint64 {
	vals := make([]uint64, records)
	offset := chunk * 4
	for i := 0; i < records; i++ {
		start := i*recordLen + offset
		vals[i] = uint64(binary.LittleEndian.Uint32(raw[start : start+4]))
	}
	return vals
}

func setupChunk(vals []uint64) *ChunkBackend {
	pi := pir.SimplePIR{}
	p := pi.PickParams(uint64(len(vals)), chunkBits, secParam, logQ)
	db := pir.MakeDB(uint64(len(vals)), chunkBits, &p, vals)
	shared := pi.Init(db.Info, p)
	start := time.Now()
	server, offline := pi.Setup(db, shared, p)
	setupMS := float64(time.Since(start).Nanoseconds()) / 1_000_000.0
	expected := make([]uint64, len(vals))
	copy(expected, vals)
	return &ChunkBackend{
		params:       p,
		db:           db,
		shared:       shared,
		server:       server,
		offline:      offline,
		expectedVals: expected,
		setupMS:      setupMS,
		offlineKB:    msgKB(offline, p),
	}
}

func setupColor(manifestPath string, subdb Subdatabase) (*ColorBackend, error) {
	dbPath := resolveDBPath(manifestPath, subdb.DatabaseFile)
	records := subdb.Records
	raw, err := loadRecords(dbPath, records, subdb.RecordBytes)
	if err != nil {
		return nil, err
	}
	if records == 0 {
		records = 1
		raw = make([]byte, recordLen)
	}
	color := &ColorBackend{color: subdb.Color, records: records}
	for chunk := 0; chunk < chunks; chunk++ {
		color.chunkDBs[chunk] = setupChunk(chunkValues(raw, records, chunk))
	}
	return color, nil
}

func runChunkQuery(cb *ChunkBackend, index int) (uint64, float64, float64, float64, float64, float64, error) {
	pi := pir.SimplePIR{}
	i := uint64(index)
	if index < 0 || index >= len(cb.expectedVals) {
		return 0, 0, 0, 0, 0, 0, fmt.Errorf("query index %d out of range [0,%d)", index, len(cb.expectedVals))
	}
	start := time.Now()
	client, query := pi.Query(i, cb.shared, cb.params, cb.db.Info)
	queryMS := float64(time.Since(start).Nanoseconds()) / 1_000_000.0
	uploadKB := msgKB(query, cb.params)
	start = time.Now()
	answer := pi.Answer(cb.db, pir.MakeMsgSlice(query), cb.server, cb.shared, cb.params)
	serverMS := float64(time.Since(start).Nanoseconds()) / 1_000_000.0
	downloadKB := msgKB(answer, cb.params)
	start = time.Now()
	recovered := pi.Recover(i, 0, cb.offline, query, answer, cb.shared, client, cb.params, cb.db.Info)
	decodeMS := float64(time.Since(start).Nanoseconds()) / 1_000_000.0
	if recovered != cb.expectedVals[index] {
		return recovered, queryMS, serverMS, decodeMS, uploadKB, downloadKB,
			fmt.Errorf("recover mismatch: got %d expected %d", recovered, cb.expectedVals[index])
	}
	return recovered, queryMS, serverMS, decodeMS, uploadKB, downloadKB, nil
}

func runManifest(manifestPath string, manifest Manifest) (Result, error) {
	colors := make([]*ColorBackend, 0, len(manifest.Subdatabases))
	cache := make(map[string]*ColorBackend)
	result := Result{
		Scheme:         manifest.Scheme,
		Height:         manifest.Height,
		Width:          manifest.Width,
		ActiveNodes:    manifest.ActiveNodes,
		QuerySamples:   manifest.QuerySamples,
		RecordBytes:    recordLen,
		ChunkBits:      int(chunkBits),
		ChunkedQueries: chunks,
		Colors:         len(manifest.Subdatabases),
	}
	for _, subdb := range manifest.Subdatabases {
		dbPath := resolveDBPath(manifestPath, subdb.DatabaseFile)
		cacheKey := fmt.Sprintf("%s|%d|%d", dbPath, subdb.Records, subdb.RecordBytes)
		color, ok := cache[cacheKey]
		if !ok {
			var err error
			color, err = setupColor(manifestPath, subdb)
			if err != nil {
				return result, err
			}
			cache[cacheKey] = color
			result.StoredRecordsPadded += color.records
			for chunk := 0; chunk < chunks; chunk++ {
				result.SetupMS += color.chunkDBs[chunk].setupMS
				result.OfflineKB += color.chunkDBs[chunk].offlineKB
			}
		}
		colors = append(colors, color)
	}
	for sample := 0; sample < manifest.QuerySamples; sample++ {
		sampleServerTotal := 0.0
		sampleServerParallel := 0.0
		for colorIdx, color := range colors {
			queryIndex := manifest.Subdatabases[colorIdx].QueryIndices[sample]
			colorServerTotal := 0.0
			for chunk := 0; chunk < chunks; chunk++ {
				_, qMS, sMS, dMS, upKB, downKB, err := runChunkQuery(color.chunkDBs[chunk], queryIndex)
				if err != nil {
					return result, fmt.Errorf("color %d sample %d chunk %d: %w", color.color, sample, chunk, err)
				}
				result.ClientQueryMS += qMS
				result.ClientDecodeMS += dMS
				result.OnlineUploadKB += upKB
				result.OnlineDownloadKB += downKB
				colorServerTotal += sMS
			}
			sampleServerTotal += colorServerTotal
			sampleServerParallel = math.Max(sampleServerParallel, colorServerTotal)
		}
		result.ServerTotalMS += sampleServerTotal
		result.ServerParallelMS += sampleServerParallel
	}
	if manifest.QuerySamples > 0 {
		divisor := float64(manifest.QuerySamples)
		result.ClientQueryMS /= divisor
		result.ClientDecodeMS /= divisor
		result.ServerTotalMS /= divisor
		result.ServerParallelMS /= divisor
		result.OnlineUploadKB /= divisor
		result.OnlineDownloadKB /= divisor
	}
	result.OnlineTotalKB = result.OnlineUploadKB + result.OnlineDownloadKB
	return result, nil
}

func isAbs(path string) bool {
	if len(path) >= 3 && path[1] == ':' {
		return true
	}
	if len(path) >= 1 && (path[0] == '/' || path[0] == '\\') {
		return true
	}
	return false
}

func resolveDBPath(manifestPath string, dbFile string) string {
	if isAbs(dbFile) {
		return dbFile
	}
	return joinDir(manifestPath, dbFile)
}

func joinDir(manifestPath string, child string) string {
	dir := manifestPath
	for i := len(manifestPath) - 1; i >= 0; i-- {
		if manifestPath[i] == '/' || manifestPath[i] == '\\' {
			dir = manifestPath[:i+1]
			break
		}
	}
	return dir + child
}

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintf(os.Stderr, "usage: smt_full_backend <manifest.json>\n")
		os.Exit(2)
	}
	manifestPath := os.Args[1]
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read manifest: %v\n", err)
		os.Exit(1)
	}
	var manifest Manifest
	if err := json.Unmarshal(raw, &manifest); err != nil {
		fmt.Fprintf(os.Stderr, "parse manifest: %v\n", err)
		os.Exit(1)
	}
	for _, subdb := range manifest.Subdatabases {
		if len(subdb.QueryIndices) != manifest.QuerySamples {
			fmt.Fprintf(os.Stderr, "color %d has %d query indices, expected %d\n",
				subdb.Color, len(subdb.QueryIndices), manifest.QuerySamples)
			os.Exit(1)
		}
	}
	result, err := runManifest(manifestPath, manifest)
	if err != nil {
		fmt.Fprintf(os.Stderr, "run backend: %v\n", err)
		os.Exit(1)
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "encode result: %v\n", err)
		os.Exit(1)
	}
	fmt.Println(string(encoded))
}
