// TIFS revision runner. Derived from smt_full_backend.go without modifying it.
// It retrieves all 32-byte records and returns them to an independent SMT verifier.
// It does not implement Merkle verification, networking, or parallel serving.
package main

import (
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
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
	Scheme        string        `json:"scheme"`
	Height        int           `json:"height"`
	Width         int           `json:"width"`
	ActiveNodes   int           `json:"active_nodes"`
	QuerySamples  int           `json:"query_samples"`
	WarmupQueries int           `json:"warmup_queries"`
	Subdatabases  []Subdatabase `json:"subdatabases"`
}

type SetupBreakdown struct {
	PickParamsMS           float64 `json:"pick_params_ms"`
	MakeDBMS               float64 `json:"make_db_ms"`
	InitMS                 float64 `json:"init_ms"`
	SetupAPIMS             float64 `json:"setup_api_ms"`
	TotalWallMS            float64 `json:"total_setup_wall_ms"`
	OfflineHintBytes       uint64  `json:"offline_hint_bytes"`
	PublicSharedStateBytes uint64  `json:"public_shared_state_bytes"`
}

type ChunkBackend struct {
	params       pir.Params
	db           *pir.Database
	shared       pir.State
	server       pir.State
	offline      pir.Msg
	expectedVals []uint64
	setup        SetupBreakdown
}

type ColorBackend struct {
	records  int
	chunkDBs [chunks]*ChunkBackend
}

type RecordResult struct {
	Color      int    `json:"color"`
	QueryIndex int    `json:"query_index"`
	RecordHex  string `json:"record_hex"`
}

type TargetResult struct {
	SampleIndex          int            `json:"sample_index"`
	ClientQueryMS        float64        `json:"client_query_ms"`
	ServerAnswerMS       float64        `json:"server_answer_ms"`
	ClientDecodeMS       float64        `json:"client_decode_ms"`
	BackendWallMS        float64        `json:"backend_wall_ms"`
	OnlineUploadBytes    uint64         `json:"online_upload_bytes"`
	OnlineDownloadBytes  uint64         `json:"online_download_bytes"`
	OnlineTotalBytes     uint64         `json:"online_total_bytes"`
	LogicalRecordQueries int            `json:"logical_record_queries"`
	ChunkQueryCount      int            `json:"chunk_query_count"`
	RecoveredRecords     []RecordResult `json:"recovered_records"`
	ChunkChecksPassed    bool           `json:"chunk_checks_passed"`
}

type ParameterRecord struct {
	Color                   int     `json:"color"`
	RecordsWithEmptyPadding int     `json:"records_with_empty_padding"`
	L                       uint64  `json:"matrix_rows_l"`
	M                       uint64  `json:"matrix_columns_m"`
	P                       uint64  `json:"plaintext_modulus_p"`
	N                       uint64  `json:"lwe_dimension_n"`
	LogQ                    uint64  `json:"ciphertext_modulus_logq"`
	Sigma                   float64 `json:"noise_sigma"`
}

type Result struct {
	SchemaVersion          int               `json:"schema_version"`
	Scheme                 string            `json:"scheme"`
	Height                 int               `json:"height"`
	Width                  int               `json:"width"`
	ActiveNodes            int               `json:"active_nodes"`
	QuerySamples           int               `json:"query_samples"`
	CompletedQueries       int               `json:"completed_queries"`
	WarmupQueries          int               `json:"warmup_queries"`
	WarmupWallMS           float64           `json:"warmup_wall_ms"`
	RecordBytes            int               `json:"record_bytes"`
	ChunkBits              int               `json:"chunk_bits"`
	ChunkedQueriesPerColor int               `json:"chunked_queries_per_color"`
	StoredRecordsPadded    int               `json:"stored_records_with_padding"`
	UniqueDatabaseFiles    int               `json:"unique_database_files"`
	Setup                  SetupBreakdown    `json:"setup"`
	Parameters             []ParameterRecord `json:"parameters"`
	Targets                []TargetResult    `json:"targets"`
	GoVersion              string            `json:"go_version"`
	GOOS                   string            `json:"goos"`
	GOARCH                 string            `json:"goarch"`
	GOMAXPROCS             int               `json:"gomaxprocs"`
	ByteAccounting         string            `json:"byte_accounting"`
	TimingScope            string            `json:"timing_scope"`
	ProcessPeakRSSBytes    *uint64           `json:"process_peak_rss_bytes"`
	ProcessPeakRSSScope    string            `json:"process_peak_rss_scope"`
}

func elapsedMS(start time.Time) float64         { return float64(time.Since(start).Nanoseconds()) / 1e6 }
func msgBytes(msg pir.Msg, p pir.Params) uint64 { return msg.Size() * p.Logq / 8 }

func publicSharedBytes(state pir.State) uint64 {
	// The upstream pir.h defines Elem as uint32_t. Count materialized matrix
	// elements, excluding Go headers/allocator overhead, not transport bytes.
	var size uint64
	for _, matrix := range state.Data {
		if matrix != nil {
			size += matrix.Size() * 4
		}
	}
	return size
}

func processPeakRSS() *uint64 {
	if runtime.GOOS != "linux" {
		return nil
	}
	raw, err := os.ReadFile("/proc/self/status")
	if err != nil {
		return nil
	}
	for _, line := range strings.Split(string(raw), "\n") {
		parts := strings.Fields(line)
		if len(parts) == 3 && parts[0] == "VmHWM:" && parts[2] == "kB" {
			value, err := strconv.ParseUint(parts[1], 10, 64)
			if err != nil {
				return nil
			}
			value *= 1024
			return &value
		}
	}
	return nil
}

func resolveDBPath(manifestPath, dbFile string) string {
	if filepath.IsAbs(dbFile) {
		return filepath.Clean(dbFile)
	}
	return filepath.Join(filepath.Dir(manifestPath), dbFile)
}

func setupChunk(vals []uint64) *ChunkBackend {
	pi := pir.SimplePIR{}
	cb := &ChunkBackend{}
	start := time.Now()
	cb.params = pi.PickParams(uint64(len(vals)), chunkBits, secParam, logQ)
	cb.setup.PickParamsMS = elapsedMS(start)
	start = time.Now()
	cb.db = pir.MakeDB(uint64(len(vals)), chunkBits, &cb.params, vals)
	cb.setup.MakeDBMS = elapsedMS(start)
	start = time.Now()
	cb.shared = pi.Init(cb.db.Info, cb.params)
	cb.setup.InitMS = elapsedMS(start)
	cb.setup.PublicSharedStateBytes = publicSharedBytes(cb.shared)
	start = time.Now()
	cb.server, cb.offline = pi.Setup(cb.db, cb.shared, cb.params)
	cb.setup.SetupAPIMS = elapsedMS(start)
	cb.setup.OfflineHintBytes = msgBytes(cb.offline, cb.params)
	cb.expectedVals = append([]uint64(nil), vals...)
	return cb
}

func setupColor(manifestPath string, subdb Subdatabase) (*ColorBackend, error) {
	if subdb.Records < 0 || subdb.RecordBytes != recordLen {
		return nil, fmt.Errorf("invalid record count/width for color %d", subdb.Color)
	}
	raw, err := os.ReadFile(resolveDBPath(manifestPath, subdb.DatabaseFile))
	if err != nil {
		return nil, err
	}
	if len(raw) != subdb.Records*recordLen {
		return nil, fmt.Errorf("color %d: got %d database bytes, expected %d", subdb.Color, len(raw), subdb.Records*recordLen)
	}
	records := subdb.Records
	if records == 0 {
		records = 1
		raw = make([]byte, recordLen)
	}
	color := &ColorBackend{records: records}
	for chunk := 0; chunk < chunks; chunk++ {
		vals := make([]uint64, records)
		for i := 0; i < records; i++ {
			vals[i] = uint64(binary.LittleEndian.Uint32(raw[i*recordLen+chunk*4 : i*recordLen+chunk*4+4]))
		}
		color.chunkDBs[chunk] = setupChunk(vals)
	}
	return color, nil
}

func runChunkQuery(cb *ChunkBackend, index int) (uint64, float64, float64, float64, uint64, uint64, error) {
	if index < 0 || index >= len(cb.expectedVals) {
		return 0, 0, 0, 0, 0, 0, fmt.Errorf("query index %d out of range [0,%d)", index, len(cb.expectedVals))
	}
	pi := pir.SimplePIR{}
	i := uint64(index)
	start := time.Now()
	client, query := pi.Query(i, cb.shared, cb.params, cb.db.Info)
	qMS := elapsedMS(start)
	upBytes := msgBytes(query, cb.params)
	start = time.Now()
	answer := pi.Answer(cb.db, pir.MakeMsgSlice(query), cb.server, cb.shared, cb.params)
	sMS := elapsedMS(start)
	downBytes := msgBytes(answer, cb.params)
	start = time.Now()
	recovered := pi.Recover(i, 0, cb.offline, query, answer, cb.shared, client, cb.params, cb.db.Info)
	dMS := elapsedMS(start)
	if recovered != cb.expectedVals[index] {
		return 0, 0, 0, 0, 0, 0, fmt.Errorf("chunk recover mismatch: got %d expected %d", recovered, cb.expectedVals[index])
	}
	return recovered, qMS, sMS, dMS, upBytes, downBytes, nil
}

func runTarget(manifest Manifest, colors []*ColorBackend, sample int) (TargetResult, error) {
	row := TargetResult{SampleIndex: sample, LogicalRecordQueries: len(colors), RecoveredRecords: make([]RecordResult, 0, len(colors))}
	start := time.Now()
	for colorIdx, color := range colors {
		subdb := manifest.Subdatabases[colorIdx]
		index := subdb.QueryIndices[sample]
		raw := make([]byte, recordLen)
		for chunk := 0; chunk < chunks; chunk++ {
			v, qMS, sMS, dMS, up, down, err := runChunkQuery(color.chunkDBs[chunk], index)
			if err != nil {
				return row, fmt.Errorf("sample %d color %d chunk %d: %w", sample, subdb.Color, chunk, err)
			}
			binary.LittleEndian.PutUint32(raw[chunk*4:chunk*4+4], uint32(v))
			row.ClientQueryMS += qMS
			row.ServerAnswerMS += sMS
			row.ClientDecodeMS += dMS
			row.OnlineUploadBytes += up
			row.OnlineDownloadBytes += down
			row.ChunkQueryCount++
		}
		row.RecoveredRecords = append(row.RecoveredRecords, RecordResult{Color: subdb.Color, QueryIndex: index, RecordHex: hex.EncodeToString(raw)})
	}
	row.BackendWallMS = elapsedMS(start)
	row.OnlineTotalBytes = row.OnlineUploadBytes + row.OnlineDownloadBytes
	row.ChunkChecksPassed = true
	return row, nil
}

func runManifest(manifestPath string, manifest Manifest) (Result, error) {
	result := Result{SchemaVersion: 1, Scheme: manifest.Scheme, Height: manifest.Height, Width: manifest.Width, ActiveNodes: manifest.ActiveNodes, QuerySamples: manifest.QuerySamples, WarmupQueries: manifest.WarmupQueries, RecordBytes: recordLen, ChunkBits: int(chunkBits), ChunkedQueriesPerColor: chunks, Parameters: make([]ParameterRecord, 0, len(manifest.Subdatabases)), Targets: make([]TargetResult, 0, manifest.QuerySamples), GoVersion: runtime.Version(), GOOS: runtime.GOOS, GOARCH: runtime.GOARCH, GOMAXPROCS: runtime.GOMAXPROCS(0), ByteAccounting: "PIR message matrix elements multiplied by Logq/8; excludes transport/framing and serialization", TimingScope: "sequential backend only; target wall includes chunk checks and record reassembly; excludes SMT verification, Python routing, process startup, network and output serialization"}
	colors := make([]*ColorBackend, 0, len(manifest.Subdatabases))
	cache := make(map[string]*ColorBackend)
	start := time.Now()
	for _, subdb := range manifest.Subdatabases {
		key := fmt.Sprintf("%s|%d|%d", resolveDBPath(manifestPath, subdb.DatabaseFile), subdb.Records, subdb.RecordBytes)
		color, found := cache[key]
		if !found {
			var err error
			color, err = setupColor(manifestPath, subdb)
			if err != nil {
				return result, err
			}
			cache[key] = color
			result.StoredRecordsPadded += color.records
			result.UniqueDatabaseFiles++
			for _, cb := range color.chunkDBs {
				result.Setup.PickParamsMS += cb.setup.PickParamsMS
				result.Setup.MakeDBMS += cb.setup.MakeDBMS
				result.Setup.InitMS += cb.setup.InitMS
				result.Setup.SetupAPIMS += cb.setup.SetupAPIMS
				result.Setup.OfflineHintBytes += cb.setup.OfflineHintBytes
				result.Setup.PublicSharedStateBytes += cb.setup.PublicSharedStateBytes
			}
		}
		colors = append(colors, color)
		p := color.chunkDBs[0].params
		result.Parameters = append(result.Parameters, ParameterRecord{Color: subdb.Color, RecordsWithEmptyPadding: color.records, L: p.L, M: p.M, P: p.P, N: p.N, LogQ: p.Logq, Sigma: p.Sigma})
	}
	result.Setup.TotalWallMS = elapsedMS(start)
	start = time.Now()
	for warm := 0; warm < manifest.WarmupQueries; warm++ {
		if _, err := runTarget(manifest, colors, warm%manifest.QuerySamples); err != nil {
			return result, fmt.Errorf("warmup %d: %w", warm, err)
		}
	}
	result.WarmupWallMS = elapsedMS(start)
	for sample := 0; sample < manifest.QuerySamples; sample++ {
		row, err := runTarget(manifest, colors, sample)
		if err != nil {
			return result, err
		}
		result.Targets = append(result.Targets, row)
		result.CompletedQueries++
	}
	result.ProcessPeakRSSBytes = processPeakRSS()
	result.ProcessPeakRSSScope = "Linux /proc/self/status VmHWM sampled after all retrievals, before JSON serialization; entire combined server/client runner including retained results, not client-only memory; null if unavailable"
	return result, nil
}

func execute() error {
	warmup := flag.Int("warmup", -1, "warmup query batches, overrides manifest warmup_queries; cycles through measured target list")
	output := flag.String("output", "", "optional JSON output file; otherwise stdout")
	maxprocs := flag.Int("gomaxprocs", 1, "Go scheduling parallelism (backend execution remains sequential)")
	flag.Parse()
	if flag.NArg() != 1 {
		return fmt.Errorf("usage: tifs_full_proof_backend [-warmup N] [-gomaxprocs N] [-output output.json] manifest.json")
	}
	if *maxprocs < 1 {
		return fmt.Errorf("gomaxprocs must be positive")
	}
	runtime.GOMAXPROCS(*maxprocs)
	manifestPath := flag.Arg(0)
	raw, err := os.ReadFile(manifestPath)
	if err != nil {
		return fmt.Errorf("read manifest: %w", err)
	}
	var manifest Manifest
	if err := json.Unmarshal(raw, &manifest); err != nil {
		return fmt.Errorf("parse manifest: %w", err)
	}
	if *warmup >= 0 {
		manifest.WarmupQueries = *warmup
	}
	if manifest.QuerySamples < 0 || manifest.WarmupQueries < 0 {
		return fmt.Errorf("query/warmup counts cannot be negative")
	}
	if manifest.QuerySamples == 0 && manifest.WarmupQueries > 0 {
		return fmt.Errorf("warmup requires at least one target")
	}
	if manifest.Width != len(manifest.Subdatabases) {
		return fmt.Errorf("width %d differs from %d logical subdatabases", manifest.Width, len(manifest.Subdatabases))
	}
	for _, subdb := range manifest.Subdatabases {
		if len(subdb.QueryIndices) != manifest.QuerySamples {
			return fmt.Errorf("color %d has %d indices, expected %d", subdb.Color, len(subdb.QueryIndices), manifest.QuerySamples)
		}
	}
	// SimplePIR emits diagnostics with fmt.Printf. Route those to stderr while
	// keeping the runner's stdout machine-readable; no library changes required.
	jsonOut := os.Stdout
	os.Stdout = os.Stderr
	result, err := runManifest(manifestPath, manifest)
	os.Stdout = jsonOut
	if err != nil {
		return err
	}
	encoded, err := json.MarshalIndent(result, "", "  ")
	if err != nil {
		return err
	}
	encoded = append(encoded, '\n')
	if *output != "" {
		return os.WriteFile(*output, encoded, 0644)
	}
	_, err = jsonOut.Write(encoded)
	return err
}

func main() {
	if err := execute(); err != nil {
		fmt.Fprintf(os.Stderr, "tifs_full_proof_backend: %v\n", err)
		os.Exit(1)
	}
}
