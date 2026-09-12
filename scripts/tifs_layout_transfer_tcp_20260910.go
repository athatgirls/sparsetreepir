// Derived fixed-Fuel-layout transfer experiment, 2026-09-10; original TCP backend preserved. This file is built
// alone in the upstream SimplePIR module. The server never loads client targets;
// the client receives only public metadata and PIR setup (or a complete cache).
// Messages use uint64-length framing and explicit uint32 matrix serialization.
package main

import (
	"bytes"
	crand "crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math/big"
	"net"
	"os"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/ahenzinger/simplepir/pir"
)

const digestChunks = 8

type ServerSub struct {
	Color        int    `json:"color"`
	Records      int    `json:"records"`
	DatabaseFile string `json:"database_file"`
}
type ServerManifest struct {
	Method       string      `json:"method"`
	Height       int         `json:"height"`
	MetadataFile string      `json:"metadata_file"`
	SlotsFile    string      `json:"slots_file"`
	CacheFile    string      `json:"cache_file"`
	Subdatabases []ServerSub `json:"subdatabases"`
}
type ChunkPublic struct {
	Params pir.Params
	Info   pir.DBinfo
}
type ColorPublic struct {
	Color   int
	Records int
	Chunks  []ChunkPublic
}
type BootstrapHeader struct {
	Schema int
	Method string
	Height int
	Colors []ColorPublic
}
type ServerChunk struct {
	Params  pir.Params
	DB      *pir.Database
	Shared  pir.State
	Server  pir.State
	Offline pir.Msg
}
type ClientChunk struct {
	Params  pir.Params
	Info    pir.DBinfo
	Shared  pir.State
	Offline pir.Msg
}
type ClientColor struct {
	Color   int
	Records int
	Chunks  []*ClientChunk
}
type ClientTarget struct {
	SlotHex string `json:"slot_hex"`
	ValueHex string `json:"value_hex"`
	TargetIndex         int    `json:"target_index"`
	LeafInputBase64 string `json:"leaf_input_base64"`
}
type ClientInput struct {
	TrustedRootHex string         `json:"trusted_root_hex"`
	Height         int            `json:"height"`
	Targets        []ClientTarget `json:"targets"`
	Warmup         int            `json:"warmup"`
}
type Entry struct {
	Left, Right uint64
	Level       int
	Pos         int
}
type Directory struct {
	Height  int
	Slots   [][]byte
	Entries map[int][]Entry
	Colors  []int
}
type Selection struct {
	Index int
	Level int
	Real  bool
}
type RecoveredSibling struct {
	Level     int    `json:"level"`
	DigestHex string `json:"digest_hex"`
}
type QueryResult struct {
	Sample             int                `json:"sample_index"`
	TargetIndex            int                `json:"target_index"`
	EndToEndMS         float64            `json:"end_to_end_ms"`
	RouteMS            float64            `json:"known_value_decode_and_routing_ms"`
	QueryMS            float64            `json:"query_generation_ms"`
	RequestResponseMS  float64            `json:"serialize_transport_answer_ms"`
	DecodeMS           float64            `json:"decode_ms"`
	VerifyMS           float64            `json:"assembly_rootcheck_ms"`
	Upload             uint64             `json:"upload_wire_bytes"`
	Download           uint64             `json:"download_wire_bytes"`
	Valid              bool               `json:"valid_root"`
	CorruptionRejected bool               `json:"corruption_rejected"`
	RecoveredSiblings  []RecoveredSibling `json:"recovered_siblings"`
	LogicalQueries     int                `json:"logical_queries"`
}
type ClientResult struct {
	Schema            int           `json:"schema"`
	Method            string        `json:"method"`
	PID               int           `json:"client_pid"`
	ServerAddress     string        `json:"server_address"`
	BootstrapMS       float64       `json:"bootstrap_ms"`
	BootstrapUpload   uint64        `json:"bootstrap_upload_wire_bytes"`
	BootstrapDownload uint64        `json:"bootstrap_download_wire_bytes"`
	MetadataBytes     int           `json:"metadata_bytes"`
	SlotsBytes        int           `json:"slots_bytes"`
	CachePayloadBytes int           `json:"cache_payload_bytes"`
	Warmup            int           `json:"warmup_queries"`
	Queries           []QueryResult `json:"queries"`
	PeakRSS           uint64        `json:"client_peak_rss_bytes"`
	Scope             string        `json:"scope"`
}
type ServerResult struct {
	Parameters []ColorPublic `json:"parameters"`
	HintMatrixBytes uint64 `json:"hint_matrix_bytes"`
	SharedMatrixBytes uint64 `json:"shared_matrix_bytes"`
	BootstrapHeaderBytes int `json:"bootstrap_header_json_bytes"`
	Schema       int       `json:"schema"`
	Method       string    `json:"method"`
	PID          int       `json:"server_pid"`
	SetupMS      float64   `json:"setup_ms"`
	Queries      int       `json:"query_batches_including_warmup"`
	AnswerMS     []float64 `json:"server_answer_ms_including_warmup"`
	ReadBytes    uint64    `json:"total_read_wire_bytes"`
	WrittenBytes uint64    `json:"total_written_wire_bytes"`
	PeakRSS      uint64    `json:"server_peak_rss_bytes"`
}
type countedConn struct {
	net.Conn
	ReadBytes, WrittenBytes uint64
}

func (c *countedConn) Read(p []byte) (int, error) {
	n, e := c.Conn.Read(p)
	c.ReadBytes += uint64(n)
	return n, e
}
func (c *countedConn) Write(p []byte) (int, error) {
	n, e := c.Conn.Write(p)
	c.WrittenBytes += uint64(n)
	return n, e
}
func ms(t time.Time) float64 { return float64(time.Since(t).Nanoseconds()) / 1e6 }
func must(err error) {
	if err != nil {
		panic(err)
	}
}
func loadJSON(path string, v any) { b, e := os.ReadFile(path); must(e); must(json.Unmarshal(b, v)) }
func saveJSON(path string, v any) {
	b, e := json.MarshalIndent(v, "", "  ")
	must(e)
	must(os.WriteFile(path, append(b, '\n'), 0644))
}
func readFile(base, name string) []byte {
	if !filepath.IsAbs(name) {
		name = filepath.Join(base, name)
	}
	b, e := os.ReadFile(name)
	must(e)
	return b
}
func u64(w io.Writer, v uint64)  { must(binary.Write(w, binary.BigEndian, v)) }
func get64(r io.Reader) uint64   { var v uint64; must(binary.Read(r, binary.BigEndian, &v)); return v }
func blob(w io.Writer, b []byte) { u64(w, uint64(len(b))); _, e := w.Write(b); must(e) }
func getBlob(r io.Reader) []byte {
	n := get64(r)
	if n > 1<<30 {
		panic("oversized blob")
	}
	b := make([]byte, n)
	_, e := io.ReadFull(r, b)
	must(e)
	return b
}
func sendFrame(w io.Writer, b []byte) { blob(w, b) }
func recvFrame(r io.Reader) ([]byte, error) {
	var n uint64
	if e := binary.Read(r, binary.BigEndian, &n); e != nil {
		return nil, e
	}
	if n > 1<<30 {
		return nil, fmt.Errorf("oversized frame")
	}
	b := make([]byte, n)
	_, e := io.ReadFull(r, b)
	return b, e
}
func putMatrices(w io.Writer, matrices []*pir.Matrix) {
	u64(w, uint64(len(matrices)))
	for _, m := range matrices {
		u64(w, m.Rows)
		u64(w, m.Cols)
		raw := make([]byte, len(m.Data)*4)
		for i, v := range m.Data {
			binary.LittleEndian.PutUint32(raw[4*i:4*i+4], uint32(v))
		}
		_, e := w.Write(raw)
		must(e)
	}
}
func getMatrices(r io.Reader) []*pir.Matrix {
	n := get64(r)
	if n > 1000 {
		panic("too many matrices")
	}
	out := make([]*pir.Matrix, 0, n)
	for k := uint64(0); k < n; k++ {
		rows, cols := get64(r), get64(r)
		if rows > 1<<28 || cols > 1<<28 || rows*cols > 1<<28 {
			panic("matrix too large")
		}
		m := pir.MatrixNew(rows, cols)
		raw := make([]byte, rows*cols*4)
		_, e := io.ReadFull(r, raw)
		must(e)
		for i := uint64(0); i < rows*cols; i++ {
			m.Set(uint64(binary.LittleEndian.Uint32(raw[i*4:i*4+4])), i/cols, i%cols)
		}
		out = append(out, m)
	}
	return out
}
func rss() uint64 {
	b, e := os.ReadFile("/proc/self/status")
	if e != nil {
		return 0
	}
	for _, line := range strings.Split(string(b), "\n") {
		p := strings.Fields(line)
		if len(p) == 3 && p[0] == "VmHWM:" {
			v, e := strconv.ParseUint(p[1], 10, 64)
			must(e)
			return v * 1024
		}
	}
	return 0
}

func serve(manifestPath, readyPath, resultPath string) {
	var manifest ServerManifest
	loadJSON(manifestPath, &manifest)
	base := filepath.Dir(manifestPath)
	start := time.Now()
	header := BootstrapHeader{Schema: 1, Method: manifest.Method, Height: manifest.Height}
	var chunks []*ServerChunk
	pi := pir.SimplePIR{}
	if manifest.Method != "full_cache" {
		for _, sub := range manifest.Subdatabases {
			raw := readFile(base, sub.DatabaseFile)
			if len(raw) != sub.Records*32 || sub.Records < 1 {
				panic("invalid db payload")
			}
			pub := ColorPublic{Color: sub.Color, Records: sub.Records}
			for k := 0; k < digestChunks; k++ {
				vals := make([]uint64, sub.Records)
				for i := range vals {
					vals[i] = uint64(binary.LittleEndian.Uint32(raw[i*32+k*4 : i*32+k*4+4]))
				}
				cb := &ServerChunk{}
				cb.Params = pi.PickParams(uint64(sub.Records), 32, 1024, 32)
				cb.DB = pir.MakeDB(uint64(sub.Records), 32, &cb.Params, vals)
				cb.Shared = pi.Init(cb.DB.Info, cb.Params)
				cb.Server, cb.Offline = pi.Setup(cb.DB, cb.Shared, cb.Params)
				chunks = append(chunks, cb)
				pub.Chunks = append(pub.Chunks, ChunkPublic{Params: cb.Params, Info: cb.DB.Info})
			}
			header.Colors = append(header.Colors, pub)
		}
	}
	result := ServerResult{Schema: 1, Method: manifest.Method, PID: os.Getpid(), SetupMS: ms(start), AnswerMS: []float64{}}
	result.Parameters = header.Colors
	for _, cb := range chunks {
		for _, matrix := range cb.Shared.Data { result.SharedMatrixBytes += uint64(len(matrix.Data))*4 }
		for _, matrix := range cb.Offline.Data { result.HintMatrixBytes += uint64(len(matrix.Data))*4 }
	}
	var boot bytes.Buffer
	headerJSON, e := json.Marshal(header)
	must(e)
	result.BootstrapHeaderBytes = len(headerJSON)
	blob(&boot, headerJSON)
	blob(&boot, readFile(base, manifest.MetadataFile))
	blob(&boot, readFile(base, manifest.SlotsFile))
	if manifest.Method == "full_cache" {
		blob(&boot, readFile(base, manifest.CacheFile))
	} else {
		for _, cb := range chunks {
			putMatrices(&boot, cb.Shared.Data)
			putMatrices(&boot, cb.Offline.Data)
		}
	}
	listener, e := net.Listen("tcp4", "127.0.0.1:0")
	must(e)
	defer listener.Close()
	saveJSON(readyPath, map[string]any{"address": listener.Addr().String(), "pid": os.Getpid()})
	connection, e := listener.Accept()
	must(e)
	defer connection.Close()
	must(connection.SetDeadline(time.Now().Add(300 * time.Second)))
	conn := &countedConn{Conn: connection}
	hello, e := recvFrame(conn)
	must(e)
	if !bytes.Equal(hello, []byte("TIFSCT1")) {
		panic("bad hello")
	}
	sendFrame(conn, boot.Bytes())
	boot.Reset()
	if manifest.Method != "full_cache" {
		for {
			packet, e := recvFrame(conn)
			if e == io.EOF {
				break
			}
			must(e)
			reader := bytes.NewReader(packet)
			n := get64(reader)
			if int(n) != len(chunks) {
				panic("variable or incorrect query width")
			}
			queries := make([]pir.Msg, n)
			for i := range queries {
				queries[i] = pir.Msg{Data: getMatrices(reader)}
			}
			if reader.Len() != 0 {
				panic("extra query bytes")
			}
			start = time.Now()
			answers := make([]pir.Msg, n)
			for i, cb := range chunks {
				answers[i] = pi.Answer(cb.DB, pir.MakeMsgSlice(queries[i]), cb.Server, cb.Shared, cb.Params)
			}
			result.AnswerMS = append(result.AnswerMS, ms(start))
			result.Queries++
			var response bytes.Buffer
			u64(&response, n)
			for _, answer := range answers {
				putMatrices(&response, answer.Data)
			}
			sendFrame(conn, response.Bytes())
		}
	} else {
		var b [1]byte
		_, e := conn.Read(b[:])
		if e != io.EOF {
			must(e)
		}
	}
	result.ReadBytes = conn.ReadBytes
	result.WrittenBytes = conn.WrittenBytes
	result.PeakRSS = rss()
	saveJSON(resultPath, result)
}

func parseDirectory(raw, slotraw []byte) Directory {
	if len(raw) < 18 || string(raw[:8]) != "TIFSMETA" {
		panic("bad directory")
	}
	h := int(binary.BigEndian.Uint16(raw[8:10]))
	n := int(binary.BigEndian.Uint32(raw[10:14]))
	nc := int(binary.BigEndian.Uint32(raw[14:18]))
	if h != 128 || len(slotraw) != n*16 {
		panic("bad slot directory")
	}
	d := Directory{Height: h, Entries: map[int][]Entry{}}
	for i := 0; i < n; i++ {
		s := append([]byte(nil), slotraw[i*16:(i+1)*16]...)
		if i > 0 && bytes.Compare(d.Slots[i-1], s) >= 0 {
			panic("unsorted slots")
		}
		d.Slots = append(d.Slots, s)
	}
	offset := 18
	for i := 0; i < nc; i++ {
		if offset+8 > len(raw) {
			panic("short directory")
		}
		c, count := int(binary.BigEndian.Uint32(raw[offset:offset+4])), int(binary.BigEndian.Uint32(raw[offset+4:offset+8]))
		offset += 8
		d.Colors = append(d.Colors, c)
		for j := 0; j < count; j++ {
			if offset+24 > len(raw) {
				panic("short row")
			}
			entry := Entry{Left: binary.BigEndian.Uint64(raw[offset : offset+8]), Right: binary.BigEndian.Uint64(raw[offset+8 : offset+16]), Level: int(binary.BigEndian.Uint16(raw[offset+16 : offset+18])), Pos: int(binary.BigEndian.Uint32(raw[offset+20 : offset+24]))}
			if entry.Left > entry.Right || entry.Right >= uint64(n) || entry.Level >= h {
				panic("invalid entry")
			}
			d.Entries[c] = append(d.Entries[c], entry)
			offset += 24
		}
		sort.Slice(d.Entries[c], func(i, j int) bool { return d.Entries[c][i].Left < d.Entries[c][j].Left })
	}
	if offset != len(raw) {
		panic("directory trailing bytes")
	}
	return d
}
func route(d Directory, slot []byte, method string) map[int]Selection {
	rank := sort.Search(len(d.Slots), func(i int) bool { return bytes.Compare(d.Slots[i], slot) >= 0 })
	if rank == len(d.Slots) || !bytes.Equal(d.Slots[rank], slot) {
		panic("client target not occupied")
	}
	selection := map[int]Selection{}
	for _, c := range d.Colors {
		entries := d.Entries[c]
		if method == "full_cache" {
			for _, e := range entries {
				if e.Left <= uint64(rank) && uint64(rank) <= e.Right {
					selection[e.Level] = Selection{Index: e.Pos, Level: e.Level, Real: true}
				}
			}
			continue
		}
		pos := sort.Search(len(entries), func(i int) bool { return entries[i].Left > uint64(rank) }) - 1
		if pos >= 0 && uint64(rank) <= entries[pos].Right {
			e := entries[pos]
			selection[c] = Selection{Index: e.Pos, Level: e.Level, Real: true}
		} else {
			v, e := crand.Int(crand.Reader, big.NewInt(int64(len(entries))))
			must(e)
			selection[c] = Selection{Index: int(v.Int64()), Level: -1, Real: false}
		}
	}
	return selection
}
func defaults(h int) [][32]byte {
	d := make([][32]byte, h+1)
	d[0] = sha256.Sum256([]byte{2})
	for i := 1; i <= h; i++ {
		d[i] = parent(d[i-1], d[i-1])
	}
	return d
}
func parent(a, b [32]byte) [32]byte {
	var raw [65]byte
	raw[0] = 1
	copy(raw[1:33], a[:])
	copy(raw[33:], b[:])
	return sha256.Sum256(raw[:])
}
func rootFor(slot, value []byte, proof [][32]byte) [32]byte {
	leaf := append([]byte{0}, value...)
	current := sha256.Sum256(leaf)
	for i, sibling := range proof {
		bit := (slot[len(slot)-1-i/8] >> uint(i%8)) & 1
		if bit == 0 {
			current = parent(current, sibling)
		} else {
			current = parent(sibling, current)
		}
	}
	return current
}

func runClient(address, inputPath, resultPath string) {
	var input ClientInput
	loadJSON(inputPath, &input)
	rootBytes, e := hex.DecodeString(input.TrustedRootHex)
	must(e)
	if len(rootBytes) != 32 || input.Height != 128 {
		panic("invalid trusted root or height")
	}
	var pinned [32]byte
	copy(pinned[:], rootBytes)
	start := time.Now()
	connection, e := net.DialTimeout("tcp4", address, 10*time.Second)
	must(e)
	must(connection.SetDeadline(time.Now().Add(300 * time.Second)))
	conn := &countedConn{Conn: connection}
	sendFrame(conn, []byte("TIFSCT1"))
	raw, e := recvFrame(conn)
	must(e)
	reader := bytes.NewReader(raw)
	var header BootstrapHeader
	must(json.Unmarshal(getBlob(reader), &header))
	if header.Height != input.Height {
		panic("unexpected height")
	}
	metadata, slots := getBlob(reader), getBlob(reader)
	directory := parseDirectory(metadata, slots)
	var colors []*ClientColor
	var cache []byte
	if header.Method == "full_cache" {
		cache = getBlob(reader)
	} else {
		for _, pub := range header.Colors {
			color := &ClientColor{Color: pub.Color, Records: pub.Records}
			if len(pub.Chunks) != digestChunks {
				panic("bad chunk count")
			}
			for _, cp := range pub.Chunks {
				color.Chunks = append(color.Chunks, &ClientChunk{Params: cp.Params, Info: cp.Info, Shared: pir.State{Data: getMatrices(reader)}, Offline: pir.Msg{Data: getMatrices(reader)}})
			}
			colors = append(colors, color)
		}
	}
	if reader.Len() != 0 {
		panic("bootstrap extra bytes")
	}
	result := ClientResult{Schema: 1, Method: header.Method, PID: os.Getpid(), ServerAddress: address, BootstrapMS: ms(start), BootstrapUpload: conn.WrittenBytes, BootstrapDownload: conn.ReadBytes, MetadataBytes: len(metadata), SlotsBytes: len(slots), CachePayloadBytes: len(cache), Warmup: input.Warmup, Scope: "Separate client/server processes; one persistent TCP connection on loopback. End-to-end includes known-value decoding and public-directory routing, query generation, serialization, transport, server answer, decode, and SMT root verification. Excludes initial bootstrap and process launch; bootstrap separately measured. Wire bytes count successful socket application reads/writes including framing, not TCP/IP headers or retransmissions."}
	def := defaults(input.Height)
	pi := pir.SimplePIR{}
	for sample := -input.Warmup; sample < len(input.Targets); sample++ {
		targetIndex := sample
		if sample < 0 {
			targetIndex = (-sample - 1) % len(input.Targets)
		}
		target := input.Targets[targetIndex]
		row := QueryResult{Sample: sample, TargetIndex: target.TargetIndex, LogicalQueries: len(colors)}
		whole := time.Now()
		phase := time.Now()
		var value [32]byte
		var slot []byte
		if target.SlotHex != "" || target.ValueHex != "" {
			decodedSlot, err := hex.DecodeString(target.SlotHex); must(err)
			decodedValue, err := hex.DecodeString(target.ValueHex); must(err)
			if len(decodedSlot) != 16 || len(decodedValue) != 32 { panic("invalid known Fuel slot/value") }
			slot = decodedSlot; copy(value[:], decodedValue)
		} else {
			record, err := base64.StdEncoding.DecodeString(target.LeafInputBase64); must(err)
			value = sha256.Sum256(record); slot = value[:16]
		}
		selection := route(directory, slot, header.Method)
		row.RouteMS = ms(phase)
		proof := append([][32]byte(nil), def[:input.Height]...)
		if header.Method == "full_cache" {
			phase = time.Now()
			for _, s := range selection {
				copy(proof[s.Level][:], cache[s.Index*32:(s.Index+1)*32])
			}
			row.DecodeMS = ms(phase)
		} else {
			phase = time.Now()
			queries := make([]pir.Msg, 0, len(colors)*digestChunks)
			states := make([]pir.State, 0, len(colors)*digestChunks)
			for _, color := range colors {
				s := selection[color.Color]
				if s.Index < 0 || s.Index >= color.Records {
					panic("route outside database")
				}
				for _, cb := range color.Chunks {
					state, query := pi.Query(uint64(s.Index), cb.Shared, cb.Params, cb.Info)
					states = append(states, state)
					queries = append(queries, query)
				}
			}
			row.QueryMS = ms(phase)
			phase = time.Now()
			up, down := conn.WrittenBytes, conn.ReadBytes
			var request bytes.Buffer
			u64(&request, uint64(len(queries)))
			for _, query := range queries {
				putMatrices(&request, query.Data)
			}
			sendFrame(conn, request.Bytes())
			answerPacket, e := recvFrame(conn)
			must(e)
			ar := bytes.NewReader(answerPacket)
			if int(get64(ar)) != len(queries) {
				panic("answer count mismatch")
			}
			answers := make([]pir.Msg, len(queries))
			for i := range answers {
				answers[i] = pir.Msg{Data: getMatrices(ar)}
			}
			if ar.Len() != 0 {
				panic("answer extra bytes")
			}
			row.Upload = conn.WrittenBytes - up
			row.Download = conn.ReadBytes - down
			row.RequestResponseMS = ms(phase)
			phase = time.Now()
			i := 0
			for _, color := range colors {
				s := selection[color.Color]
				var recovered [32]byte
				for k, cb := range color.Chunks {
					v := pi.Recover(uint64(s.Index), 0, cb.Offline, queries[i], answers[i], cb.Shared, states[i], cb.Params, cb.Info)
					binary.LittleEndian.PutUint32(recovered[k*4:k*4+4], uint32(v))
					i++
				}
				if s.Real {
					proof[s.Level] = recovered
				}
			}
			row.DecodeMS = ms(phase)
		}
		phase = time.Now()
		row.Valid = rootFor(slot, value[:], proof) == pinned
		if !row.Valid {
			panic(fmt.Sprintf("root check failed method=%s sample=%d", header.Method, sample))
		}
		row.VerifyMS = ms(phase)
		row.EndToEndMS = ms(whole)
		// Retain the actual used PIR/cache output only after the timed audit.
		// Its allocation and later GC remain part of this evidence-enabled run.
		levels := make([]int, 0, len(selection))
		for _, selected := range selection {
			if selected.Real {
				levels = append(levels, selected.Level)
			}
		}
		sort.Ints(levels)
		for _, level := range levels {
			row.RecoveredSiblings = append(row.RecoveredSiblings, RecoveredSibling{Level: level, DigestHex: hex.EncodeToString(proof[level][:])})
		}
		// Negative control is excluded from the measured end-to-end interval.
		bad := append([][32]byte(nil), proof...)
		corruptLevel := -1
		for _, selected := range selection {
			if selected.Real && (corruptLevel < 0 || selected.Level < corruptLevel) {
				corruptLevel = selected.Level
			}
		}
		if corruptLevel < 0 {
			panic("certificate study requires a real proof sibling")
		}
		bad[corruptLevel][0] ^= 1
		row.CorruptionRejected = rootFor(slot, value[:], bad) != pinned
		if !row.CorruptionRejected {
			panic("corruption accepted")
		}
		if sample >= 0 {
			result.Queries = append(result.Queries, row)
		}
	}
	must(connection.Close())
	result.PeakRSS = rss()
	saveJSON(resultPath, result)
}

func main() {
	mode := flag.String("mode", "", "server or client")
	manifest := flag.String("manifest", "", "server-only manifest")
	ready := flag.String("ready", "", "server readiness file")
	input := flag.String("input", "", "client-only target records and pinned root")
	address := flag.String("address", "", "loopback server address")
	result := flag.String("result", "", "output JSON")
	flag.Parse()
	runtime.GOMAXPROCS(1)
	os.Stdout = os.Stderr
	if *mode == "server" {
		serve(*manifest, *ready, *result)
	} else if *mode == "client" {
		host, _, e := net.SplitHostPort(*address)
		must(e)
		if host != "127.0.0.1" {
			panic("prototype restricted to loopback")
		}
		runClient(*address, *input, *result)
	} else {
		panic("mode must be server or client")
	}
}
