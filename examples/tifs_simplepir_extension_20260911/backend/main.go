// Persistent same-process proof pipeline over unmodified official SimplePIR.
// Only the base-p input/output integer width is extended from uint64 to 256 bits.
package main

import (
	"bytes"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"math/big"
	"math/rand"
	"os"
	"runtime"
	"runtime/debug"
	"sort"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/ahenzinger/simplepir/pir"
)

type Obj = map[string]interface{}
type Interval struct {
	Left   int `json:"left"`
	Right  int `json:"right"`
	Level  int `json:"level"`
	Record int `json:"record"`
}
type Need struct {
	Record int `json:"record"`
	Level  int `json:"level"`
}
type Target struct {
	ID     interface{} `json:"id"`
	Slot   string      `json:"slot_hex"`
	Value  string      `json:"value_hex"`
	Needed []Need      `json:"needed"`
}
type Input struct {
	Mode            string       `json:"mode"`
	Height          int          `json:"height"`
	Root            string       `json:"root_hex"`
	Defaults        []string     `json:"default_hashes"`
	Slots           []string     `json:"occupied_slots_hex"`
	Records         []string     `json:"records"`
	Intervals       []Interval   `json:"record_intervals"`
	Buckets         [][]int      `json:"buckets"`
	BucketIntervals [][]Interval `json:"bucket_intervals"`
	Candidates      [][]int      `json:"hash_candidates"`
	Targets         []Target     `json:"targets"`
	Seed            int64        `json:"seed"`
	PIR             struct {
		Batch int `json:"batch_size"`
	} `json:"pir"`
}

// Public excludes record values and target/expected-route data. It is actually
// serialized and parsed into a separate client directory before online routing.
type Public struct {
	Mode       string     `json:"mode"`
	Height     int        `json:"height"`
	Root       string     `json:"root_hex"`
	Defaults   []string   `json:"default_hashes"`
	Slots      []string   `json:"occupied_slots_hex"`
	Intervals  []Interval `json:"record_intervals"`
	Buckets    [][]int    `json:"buckets"`
	Candidates [][]int    `json:"hash_candidates,omitempty"`
	Batch      int        `json:"batch_size"`
}
type Forest struct {
	nodes    []Interval
	children [][]int
	roots    []int
}

func forest(nodes []Interval) Forest {
	f := Forest{nodes: nodes, children: make([][]int, len(nodes))}
	order := make([]int, len(nodes))
	for i := range order {
		order[i] = i
	}
	sort.Slice(order, func(i, j int) bool {
		a, b := nodes[order[i]], nodes[order[j]]
		if a.Left != b.Left {
			return a.Left < b.Left
		}
		return a.Right > b.Right
	})
	stack := []int{}
	for _, i := range order {
		x := nodes[i]
		for len(stack) > 0 && x.Left > nodes[stack[len(stack)-1]].Right {
			stack = stack[:len(stack)-1]
		}
		if len(stack) == 0 {
			f.roots = append(f.roots, i)
		} else {
			p := stack[len(stack)-1]
			require(x.Right <= nodes[p].Right, "non-laminar public intervals")
			require(x.Left != nodes[p].Left || x.Right != nodes[p].Right, "duplicate public interval")
			f.children[p] = append(f.children[p], i)
		}
		stack = append(stack, i)
	}
	return f
}
func (f *Forest) stab(rank int) []Interval {
	out := []Interval{}
	list := f.roots
	for len(list) > 0 {
		at := sort.Search(len(list), func(i int) bool { return f.nodes[list[i]].Left > rank }) - 1
		if at < 0 {
			break
		}
		idx := list[at]
		x := f.nodes[idx]
		if x.Right < rank {
			break
		}
		out = append(out, x)
		list = f.children[idx]
	}
	return out
}

type Directory struct {
	pub       Public
	forest    Forest
	sorted    [][]Interval
	positions []map[int]int
	defaults  [][]byte
	root      []byte
}

func directory(pub Public) *Directory {
	d := &Directory{pub: pub, forest: forest(pub.Intervals), positions: make([]map[int]int, len(pub.Buckets)), sorted: make([][]Interval, len(pub.Buckets)), root: unhex(pub.Root)}
	for _, x := range pub.Defaults {
		d.defaults = append(d.defaults, unhex(x))
	}
	for b, ids := range pub.Buckets {
		d.positions[b] = map[int]int{}
		for p, r := range ids {
			d.positions[b][r] = p
			d.sorted[b] = append(d.sorted[b], pub.Intervals[r])
		}
		sort.Slice(d.sorted[b], func(i, j int) bool { return d.sorted[b][i].Left < d.sorted[b][j].Left })
	}
	return d
}

type Pick struct{ Bucket, Position, Record, Level int }

// This is the original empty-slot-first / random-eviction cuckoo rule, with
// deterministic insertion order and independent experimental RNG in Go.
func cuckoo(batch []int, candidates [][]int, buckets int, rng *rand.Rand) []int {
	owner := make([]int, buckets)
	for i := range owner {
		owner[i] = -1
	} // reset every query
	var insert func(int, int)
	insert = func(key, attempt int) {
		require(attempt <= 500, "PBC cuckoo exceeded 500 recursive attempts; no global rehash or target replacement")
		for _, b := range candidates[key] {
			if owner[b] < 0 {
				owner[b] = key
				return
			}
		}
		b := candidates[key][rng.Intn(len(candidates[key]))]
		old := owner[b]
		owner[b] = key
		insert(old, attempt+1)
	}
	for _, key := range batch {
		insert(key, 0)
	}
	seen := map[int]bool{}
	for _, key := range owner {
		if key >= 0 {
			require(!seen[key], "duplicate cuckoo owner")
			seen[key] = true
		}
	}
	require(len(seen) == len(batch), "cuckoo lost record")
	return owner
}
func (d *Directory) route(slot string, rng *rand.Rand) ([]Pick, []Interval) {
	rank := sort.SearchStrings(d.pub.Slots, slot)
	require(rank < len(d.pub.Slots) && d.pub.Slots[rank] == slot, "target is not occupied")
	out := []Pick{}
	needed := []Interval{}
	if d.pub.Mode == "ab" || d.pub.Mode == "first_fit" {
		for b, rows := range d.sorted {
			p := Pick{Bucket: b, Level: -1, Record: -1}
			i := sort.Search(len(rows), func(i int) bool { return rows[i].Left > rank }) - 1
			if i >= 0 && rows[i].Right >= rank {
				x := rows[i]
				p.Position = d.positions[b][x.Record]
				p.Record = x.Record
				p.Level = x.Level
				needed = append(needed, x)
			} else if len(d.pub.Buckets[b]) > 0 {
				p.Position = rng.Intn(len(d.pub.Buckets[b]))
				p.Record = d.pub.Buckets[b][p.Position]
			}
			out = append(out, p)
		}
	} else {
		needed = d.forest.stab(rank)
		require(len(needed) <= d.pub.Batch, "proof wider than public batch size")
		batch := []int{}
		levels := map[int]int{}
		seen := map[int]bool{}
		for _, x := range needed {
			batch = append(batch, x.Record)
			seen[x.Record] = true
			levels[x.Record] = x.Level
		}
		for len(batch) < d.pub.Batch {
			r := rng.Intn(len(d.pub.Intervals))
			if !seen[r] {
				seen[r] = true
				batch = append(batch, r)
			}
		}
		if d.pub.Mode == "flat" {
			for _, r := range batch {
				level := -1
				if l, ok := levels[r]; ok {
					level = l
				}
				out = append(out, Pick{0, d.positions[0][r], r, level})
			}
		} else {
			owner := cuckoo(batch, d.pub.Candidates, len(d.pub.Buckets), rng)
			for b, r := range owner {
				p := Pick{Bucket: b, Record: r, Level: -1}
				if r >= 0 {
					var ok bool
					p.Position, ok = d.positions[b][r]
					require(ok, "PBC map lacks record")
					if l, ok := levels[r]; ok {
						p.Level = l
					}
				} else if len(d.pub.Buckets[b]) > 0 {
					p.Position = rng.Intn(len(d.pub.Buckets[b]))
					p.Record = d.pub.Buckets[b][p.Position]
				}
				out = append(out, p)
			}
		}
	}
	require(len(needed) > 0 && len(needed) <= d.pub.Batch, "invalid online proof width")
	return out, needed
}

func require(ok bool, s string) {
	if !ok {
		panic(s)
	}
}
func must(e error) {
	if e != nil {
		panic(e)
	}
}
func ms(t time.Time) float64 { return float64(time.Since(t).Nanoseconds()) / 1e6 }
func sha(b []byte) string    { x := sha256.Sum256(b); return hex.EncodeToString(x[:]) }
func unhex(s string) []byte {
	s = strings.TrimPrefix(s, "0x")
	if len(s)%2 != 0 {
		s = "0" + s
	}
	b, e := hex.DecodeString(s)
	must(e)
	require(len(b) > 0, "empty hex")
	return b
}
func slotkey(s string, height int) string {
	b := unhex(s)
	n := (height + 7) / 8
	require(len(b) <= n, "coordinate too wide")
	out := make([]byte, n)
	copy(out[n-len(b):], b)
	if height%8 != 0 {
		require(out[0]>>uint(height%8) == 0, "coordinate exceeds tree height")
	}
	return hex.EncodeToString(out)
}
func rootOf(value, slot []byte, proof [][]byte) []byte {
	x := sha256.Sum256(append([]byte{0}, value...))
	for level, sibling := range proof {
		require(len(sibling) == 32, "invalid sibling width")
		buf := make([]byte, 65)
		buf[0] = 1
		if slot[len(slot)-1-level/8]>>uint(level%8)&1 == 1 {
			copy(buf[1:33], sibling)
			copy(buf[33:], x[:])
		} else {
			copy(buf[1:33], x[:])
			copy(buf[33:], sibling)
		}
		x = sha256.Sum256(buf)
	}
	return append([]byte{}, x[:]...)
}
func peakRSS() uint64 {
	var r syscall.Rusage
	must(syscall.Getrusage(syscall.RUSAGE_SELF, &r))
	return uint64(r.Maxrss) * 1024
}
func exactNe(bits, p uint64) uint64 {
	product := big.NewInt(1)
	base := new(big.Int).SetUint64(p)
	bound := new(big.Int).Lsh(big.NewInt(1), uint(bits))
	var n uint64
	for product.Cmp(bound) < 0 {
		product.Mul(product, base)
		n++
	}
	return n
}
func make256(records [][]byte, p pir.Params) *pir.Database {
	db := pir.SetupDB(uint64(len(records)), 256, &p)
	require(db.Info.Packing == 0 && db.Info.Ne == exactNe(256, p.P), "invalid long-record decomposition")
	db.Data = pir.MatrixZeros(p.L, p.M)
	base := new(big.Int).SetUint64(p.P)
	for i, raw := range records {
		require(len(raw) == 32, "record is not 32 bytes")
		v := new(big.Int).SetBytes(raw)
		digit := new(big.Int)
		for j := uint64(0); j < db.Info.Ne; j++ {
			v.QuoRem(v, base, digit)
			db.Data.Set(digit.Uint64(), (uint64(i)/p.M)*db.Info.Ne+j, uint64(i)%p.M)
		}
		require(v.Sign() == 0, "insufficient base-p capacity")
	}
	db.Data.Sub(p.P / 2)
	return db
}

type Backend struct {
	p                                  pir.Params
	db                                 *pir.Database
	serverShared, clientShared, server pir.State
	hint                               pir.Msg
	clientInfo                         pir.DBinfo
}

// Same modular subtraction, offset, rounding, and centering as upstream Recover.
// Its uint64 final reconstruction is replaced by big.Int; no change to LWE math.
func recover256(index uint64, b *Backend, state pir.State, query, answer pir.Msg) []byte {
	p := b.p
	info := b.clientInfo
	q := uint64(1) << p.Logq
	mask := q - 1
	var offset uint64
	for j := uint64(0); j < p.M; j++ {
		offset += (p.P / 2) * query.Data[0].Get(j, 0)
	}
	offset = q - offset%q
	product := pir.MatrixMul(b.hint.Data[0], state.Data[0])
	value := big.NewInt(0)
	coefficient := big.NewInt(1)
	base := new(big.Int).SetUint64(p.P)
	for j := uint64(0); j < info.Ne; j++ {
		row := (index/p.M)*info.Ne + j
		residual := (answer.Data[0].Get(row, 0) - product.Get(row, 0)) & mask
		denoised := p.Round(residual + offset)
		digit := (denoised + p.P/2) % q % p.P
		term := new(big.Int).Mul(new(big.Int).SetUint64(digit), coefficient)
		value.Add(value, term)
		coefficient.Mul(coefficient, base)
	}
	require(value.BitLen() <= 256, "decoded record exceeds 256 bits")
	return value.FillBytes(make([]byte, 32))
}

// Actual self-describing, uncompressed binary frame: message count, per-message
// matrix count, per-matrix rows/cols, followed by uint32 little-endian elements.
func encode(msgs []pir.Msg) ([]byte, uint64) {
	size := 8
	var payload uint64
	for _, msg := range msgs {
		size += 8
		for _, m := range msg.Data {
			require(uint64(len(m.Data)) == m.Rows*m.Cols, "bad matrix shape")
			size += 16 + 4*len(m.Data)
			payload += m.Size() * 4
		}
	}
	wire := make([]byte, size)
	pos := 0
	put := func(v uint64) { binary.LittleEndian.PutUint64(wire[pos:pos+8], v); pos += 8 }
	put(uint64(len(msgs)))
	for _, msg := range msgs {
		put(uint64(len(msg.Data)))
		for _, m := range msg.Data {
			put(m.Rows)
			put(m.Cols)
			for _, v := range m.Data {
				binary.LittleEndian.PutUint32(wire[pos:pos+4], uint32(v))
				pos += 4
			}
		}
	}
	require(pos == len(wire), "encode frame mismatch")
	return wire, payload
}
func decode(wire []byte) []pir.Msg {
	pos := 0
	get := func() uint64 {
		require(pos+8 <= len(wire), "truncated frame")
		v := binary.LittleEndian.Uint64(wire[pos : pos+8])
		pos += 8
		return v
	}
	count := get()
	require(count <= uint64(len(wire)/8), "invalid message count")
	out := make([]pir.Msg, int(count))
	for i := range out {
		count := get()
		require(count <= uint64(len(wire)/16), "invalid matrix count")
		for j := uint64(0); j < count; j++ {
			rows, cols := get(), get()
			require(rows > 0 && cols > 0 && rows <= uint64(len(wire)/4)/cols, "invalid matrix dimensions")
			require(rows*cols <= uint64((len(wire)-pos)/4), "truncated matrix")
			m := pir.MatrixNew(rows, cols)
			for r := uint64(0); r < rows; r++ {
				for c := uint64(0); c < cols; c++ {
					m.Set(uint64(binary.LittleEndian.Uint32(wire[pos:pos+4])), r, c)
					pos += 4
				}
			}
			out[i].Data = append(out[i].Data, m)
		}
	}
	require(pos == len(wire), "trailing frame bytes")
	return out
}
func roundtrip(msgs []pir.Msg) ([]pir.Msg, uint64, uint64) {
	wire, payload := encode(msgs)
	return decode(wire), payload, uint64(len(wire))
}

func validate(in *Input) [][]byte {
	require(in.Mode == "ab" || in.Mode == "pbc" || in.Mode == "flat" || in.Mode == "first_fit", "unsupported method")
	require(in.Height > 0 && in.Height <= 4096, "invalid height")
	require(len(unhex(in.Root)) == 32, "invalid root")
	require(len(in.Defaults) == in.Height, "defaults do not cover original height")
	for _, s := range in.Defaults {
		require(len(unhex(s)) == 32, "invalid default width")
	}
	for i, s := range in.Slots {
		in.Slots[i] = slotkey(s, in.Height)
		if i > 0 {
			require(in.Slots[i-1] < in.Slots[i], "slots not sorted and unique")
		}
	}
	require(len(in.Slots) > 1 && len(in.Records) > 1 && len(in.Targets) > 0, "input has no usable records/targets")
	require(in.PIR.Batch >= 2 && in.PIR.Batch <= len(in.Records), "invalid public batch size")
	require(len(in.Intervals) == len(in.Records), "global intervals must cover records")
	raw := make([][]byte, len(in.Records))
	for i, s := range in.Records {
		raw[i] = unhex(s)
		require(len(raw[i]) == 32, "record is not 32 bytes")
		x := in.Intervals[i]
		require(x.Record == i && x.Left >= 0 && x.Left <= x.Right && x.Right < len(in.Slots) && x.Level >= 0 && x.Level < in.Height, "invalid canonical interval")
	}
	count := len(in.Buckets)
	require(count > 0, "no buckets")
	if in.Mode == "flat" {
		require(count == 1, "flat must initialize exactly one database")
	}
	if in.Mode == "ab" {
		require(count == in.PIR.Batch, "AB buckets must equal m")
	}
	if in.Mode == "first_fit" {
		require(count >= in.PIR.Batch, "FF fewer than maximum proof width")
	}
	if in.Mode == "pbc" {
		require(count == (3*in.PIR.Batch+1)/2 && count >= 3, "PBC bucket factor must be 1.5")
		require(len(in.Candidates) == len(raw), "missing PBC candidates")
	}
	copies := make([]int, len(raw))
	membership := make([]map[int]bool, count)
	for b, ids := range in.Buckets {
		membership[b] = map[int]bool{}
		for j, r := range ids {
			require(r >= 0 && r < len(raw) && !membership[b][r], "invalid or repeated bucket record")
			membership[b][r] = true
			copies[r]++
			if len(in.BucketIntervals) > 0 {
				require(len(in.BucketIntervals) == count && len(in.BucketIntervals[b]) == len(ids), "bucket interval shape mismatch")
				require(in.BucketIntervals[b][j] == in.Intervals[r], "bucket interval does not match canonical record")
			}
		}
		if in.Mode == "ab" || in.Mode == "first_fit" {
			iv := make([]Interval, len(ids))
			for i, r := range ids {
				iv[i] = in.Intervals[r]
			}
			sort.Slice(iv, func(i, j int) bool { return iv[i].Left < iv[j].Left })
			for i := 1; i < len(iv); i++ {
				require(iv[i-1].Right < iv[i].Left, "structured bucket intervals overlap")
			}
		}
	}
	for r, n := range copies {
		if in.Mode == "pbc" {
			require(n == 3 && len(in.Candidates[r]) == 3, "PBC must have three record copies")
			seen := map[int]bool{}
			for _, b := range in.Candidates[r] {
				require(b >= 0 && b < count && !seen[b] && membership[b][r], "PBC candidate does not match placement")
				seen[b] = true
			}
		} else {
			require(n == 1, "layout must partition every record exactly once")
		}
	}
	for i := range in.Targets {
		in.Targets[i].Slot = slotkey(in.Targets[i].Slot, in.Height)
		require(len(unhex(in.Targets[i].Value)) > 0, "empty known value")
	}
	return raw
}

func execute(inputFile, outputFile string, warmup int) (rc int) {
	report := Obj{"status": "running", "queries": []Obj{}, "warmups": []Obj{}}
	setup := Obj{}
	parameters := Obj{}
	report["setup"] = setup
	report["parameters"] = parameters
	defer func() {
		if e := recover(); e != nil {
			report["status"] = "failed"
			report["error"] = fmt.Sprint(e)
			rc = 2
			fmt.Fprintln(os.Stderr, e)
		}
		setup["combined_peak_rss_final_bytes"] = peakRSS()
		b, e := json.MarshalIndent(report, "", "  ")
		if e != nil {
			fmt.Fprintln(os.Stderr, e)
			rc = 2
			return
		}
		if e = os.WriteFile(outputFile, append(b, '\n'), 0644); e != nil {
			fmt.Fprintln(os.Stderr, e)
			rc = 2
		}
	}()
	totalStart := time.Now()
	part := totalStart
	inputBytes, e := os.ReadFile(inputFile)
	must(e)
	var in Input
	must(json.Unmarshal(inputBytes, &in))
	raw := validate(&in)
	require(warmup >= 0 && warmup <= 1000, "invalid warmup count")
	if in.Seed == 0 {
		in.Seed = 20260911
	}
	setup["input_read_validate_ms"] = ms(part)
	report["input_sha256"] = sha(inputBytes)
	part = time.Now()
	public := Public{in.Mode, in.Height, in.Root, in.Defaults, in.Slots, in.Intervals, in.Buckets, in.Candidates, in.PIR.Batch}
	metadata, e := json.Marshal(public)
	must(e)
	var clientPublic Public
	must(json.Unmarshal(metadata, &clientPublic))
	dir := directory(clientPublic)
	setup["public_metadata_roundtrip_and_directory_ms"] = ms(part)
	setup["public_metadata_serialized_bytes"] = len(metadata)
	capacity := 0
	totalRecords := 0
	loads := []int{}
	for _, ids := range in.Buckets {
		if len(ids) > capacity {
			capacity = len(ids)
		}
		totalRecords += len(ids)
		loads = append(loads, len(ids))
	}
	require(capacity > 0, "empty layout")
	pi := pir.SimplePIR{}
	part = time.Now()
	p := pi.PickParams(uint64(capacity), 256, 1024, 32)
	require(p.N == 1024 && p.Logq == 32 && p.Sigma == 6.4 && p.P == 991 && p.M <= 8192, "outside frozen official parameter row n1024/logq32/sigma6.4/p991/M<=8192")
	ne := exactNe(256, p.P)
	require(ne == 26 && p.L%ne == 0 && p.L*p.M >= uint64(capacity)*ne, "invalid long-record dimensions")
	setup["parameter_selection_ms"] = ms(part)
	backends := make([]*Backend, len(in.Buckets))
	metrics := []Obj{}
	var hintPayload, hintFramed, aPayload, aFramed, encodedBytes, unsquishedBytes uint64
	var makeMS, initMS, setupMS, aRoundMS, hintRoundMS, infoRoundMS float64
	for bucket, ids := range in.Buckets {
		cb := &Backend{p: p}
		records := make([][]byte, len(ids))
		for i, r := range ids {
			records[i] = raw[r]
		}
		if len(records) == 0 {
			records = [][]byte{make([]byte, 32)}
		}
		part = time.Now()
		cb.db = make256(records, p)
		makeTime := ms(part)
		makeMS += makeTime
		before := cb.db.Data.Size() * 4
		unsquishedBytes += before
		part = time.Now()
		cb.serverShared = pi.Init(cb.db.Info, p)
		initTime := ms(part)
		initMS += initTime
		part = time.Now()
		loaded, ap, af := roundtrip([]pir.Msg{pir.MakeMsg(cb.serverShared.Data...)})
		cb.clientShared = pir.MakeState(loaded[0].Data...)
		aTime := ms(part)
		aRoundMS += aTime
		aPayload += ap
		aFramed += af
		part = time.Now()
		server, hint := pi.Setup(cb.db, cb.serverShared, p)
		cb.server = server
		setupTime := ms(part)
		setupMS += setupTime
		part = time.Now()
		loaded, hp, hf := roundtrip([]pir.Msg{hint})
		cb.hint = loaded[0]
		hTime := ms(part)
		hintRoundMS += hTime
		hintPayload += hp
		hintFramed += hf
		part = time.Now()
		infoWire, e := json.Marshal(cb.db.Info)
		must(e)
		must(json.Unmarshal(infoWire, &cb.clientInfo))
		iTime := ms(part)
		infoRoundMS += iTime
		encoded := cb.db.Data.Size() * 4
		encodedBytes += encoded
		metrics = append(metrics, Obj{"bucket": bucket, "records": len(ids), "initialized_records": len(records), "params": p, "db_info": cb.clientInfo, "make_database_ms": makeTime, "init_public_A_ms": initTime, "setup_hint_and_squish_ms": setupTime, "public_A_roundtrip_ms": aTime, "hint_roundtrip_ms": hTime, "db_info_roundtrip_ms": iTime, "public_A_matrix_bytes": ap, "public_A_framed_bytes": af, "hint_matrix_bytes": hp, "hint_framed_bytes": hf, "db_info_json_bytes": len(infoWire), "encoded_db_bytes": encoded, "unsquished_db_matrix_bytes": before, "rounded_record_capacity": p.L / ne * p.M})
		backends[bucket] = cb
	}
	setup["make_database_ms"] = makeMS
	setup["init_public_A_ms"] = initMS
	setup["setup_hint_and_squish_ms"] = setupMS
	setup["public_A_roundtrip_ms"] = aRoundMS
	setup["hint_roundtrip_ms"] = hintRoundMS
	setup["db_info_roundtrip_ms"] = infoRoundMS
	setup["hint_matrix_bytes"] = hintPayload
	setup["hint_framed_bytes"] = hintFramed
	setup["public_A_matrix_bytes"] = aPayload
	setup["public_A_framed_bytes"] = aFramed
	var dbInfoBytes int
	for _, x := range metrics {
		dbInfoBytes += x["db_info_json_bytes"].(int)
	}
	setup["db_info_serialized_bytes"] = dbInfoBytes
	setup["bootstrap_payload_bytes"] = hintPayload + aPayload + uint64(len(metadata)+dbInfoBytes)
	setup["bootstrap_framed_components_bytes"] = hintFramed + aFramed + uint64(len(metadata)+dbInfoBytes)
	setup["setup_server_to_client_serialized_components_bytes"] = hintFramed + aFramed + uint64(len(metadata)+dbInfoBytes)
	setup["setup_client_to_server_bytes"] = 0
	setup["active_digest_payload_bytes"] = len(raw) * 32
	setup["replicated_record_payload_bytes"] = totalRecords * 32
	setup["max_padded_bucket_payload_bytes"] = len(backends) * capacity * 32
	setup["backend_rounded_raw_payload_bytes"] = uint64(len(backends)) * p.L / ne * p.M * 32
	setup["unsquished_db_matrix_bytes"] = unsquishedBytes
	setup["encoded_db_bytes"] = encodedBytes
	setup["bucket_metrics"] = metrics
	setup["initialized_databases"] = len(backends)
	setup["persistent_setup_wall_ms"] = ms(totalStart)
	runtime.GC()
	setup["combined_peak_rss_after_setup_bytes"] = peakRSS()
	parameters["mode"] = in.Mode
	parameters["height"] = in.Height
	parameters["records"] = len(raw)
	parameters["batch_size_m"] = in.PIR.Batch
	parameters["bucket_count"] = len(in.Buckets)
	parameters["bucket_loads"] = loads
	parameters["max_bucket_records"] = capacity
	calls := len(backends)
	if in.Mode == "flat" {
		calls = in.PIR.Batch
	}
	parameters["PIR_calls_per_proof"] = calls
	parameters["params"] = p
	parameters["base_p_digits_per_record"] = ne
	parameters["record_bytes"] = 32
	parameters["rounded_entries_per_bucket"] = p.L / ne * p.M
	parameters["pir_dimensions"] = []uint64{p.L, p.M}
	parameters["squished_dimensions"] = []uint64{p.L, (p.M + 2) / 3}
	parameters["compression"] = "matrix frames none; server DB official 3x10-bit squishing"
	parameters["parameter_policy"] = "Official PickParams(max actual bucket load,256,1024,32); one common L/M for all buckets in a layout. Flat uses N once. Fixed official params.csv first row: M<=8192,p=991,sigma=6.4. No per-target parameter changes."
	parameters["security_scope"] = "Unmodified official LWE parameter table; no new security estimate or certification"
	parameters["experiment_seed"] = in.Seed
	parameters["cuckoo_max_attempts"] = 500
	parameters["source_commit"] = "e9020b03bf2872c75b8954e749e32408b5db87ed"
	parameters["go_version"] = runtime.Version()
	parameters["gomaxprocs"] = runtime.GOMAXPROCS(0)
	parameters["process_model"] = "one sequential persistent client/server process; true hints; expanded A; no network"
	report["scope"] = "Persistent same-process serialized proof pipeline. Timed path: public routing, Query, actual uncompressed matrix encode/decode, Answer, encode/decode, 256-bit Recover width wrapper using true hint, original-level/default restoration and trusted-root verification. Input-oracle checks and three negative checks are outside timing. Setup includes read/validation and backend preparation, but excludes external tree/layout construction. Combined RSS includes both roles, input/oracle, directories, transients and validation output."
	report["long_record_scope"] = "Unmodified official Init/Setup/Query/Answer, standard vertical base-p long-record representation. MakeDB input decomposition and Recover final reconstruction use big.Int for 256 bits; modular denoising and rounding follow upstream Recover exactly. No eight-scalar decomposition or FakeSetup."
	report["routing_provenance"] = "AB/FF sorted public intervals preserve original bucket positions. Flat and PBC use a public laminar forest, pad to m distinct existing record IDs. PBC candidates/placement are exported from official C++ utils; Go transcribes empty-slot-first/random-eviction cuckoo with fixed batch insertion order, per-query cleared table, independent experiment RNG and 500 attempts. This is not a byte-identical C++ unordered_map eviction trace."
	queryRows := []Obj{}
	warmupRows := []Obj{}
	report["queries"] = queryRows
	report["warmups"] = warmupRows
	secretSeen := map[string]bool{}
	querySeen := map[string]bool{}
	one := func(target Target, ordinal int, isWarmup bool) Obj {
		row := Obj{"target_id": fmt.Sprint(target.ID), "slot_hex": target.Slot, "warmup": isWarmup}
		// Decode the private value/coordinate before the measured request path.
		value, slot := unhex(target.Value), unhex(target.Slot)
		start := time.Now()
		part := start
		rng := rand.New(rand.NewSource(in.Seed + int64(ordinal)))
		picks, needed := dir.route(target.Slot, rng)
		row["route_ms"] = ms(part)
		require(len(picks) == calls, "variable online call count")
		states := make([]pir.State, len(picks))
		queries := make([]pir.Msg, len(picks))
		answers := make([]pir.Msg, len(picks))
		part = time.Now()
		for i, pick := range picks {
			b := backends[pick.Bucket]
			states[i], queries[i] = pi.Query(uint64(pick.Position), b.clientShared, b.p, b.clientInfo)
		}
		row["query_ms"] = ms(part)
		part = time.Now()
		serverQueries, qp, qf := roundtrip(queries)
		row["query_roundtrip_ms"] = ms(part)
		part = time.Now()
		for i, pick := range picks {
			b := backends[pick.Bucket]
			answers[i] = pi.Answer(b.db, pir.MakeMsgSlice(serverQueries[i]), b.server, b.serverShared, b.p)
		}
		row["answer_ms"] = ms(part)
		part = time.Now()
		clientAnswers, ap, af := roundtrip(answers)
		row["answer_roundtrip_ms"] = ms(part)
		part = time.Now()
		recovered := make([][]byte, len(picks))
		for i, pick := range picks {
			recovered[i] = recover256(uint64(pick.Position), backends[pick.Bucket], states[i], queries[i], clientAnswers[i])
		}
		row["decode_ms"] = ms(part)
		part = time.Now()
		proof := append([][]byte{}, dir.defaults...)
		levels := map[int]bool{}
		for i, pick := range picks {
			if pick.Level >= 0 {
				require(pick.Level < in.Height && !levels[pick.Level], "invalid/duplicate proof level")
				levels[pick.Level] = true
				proof[pick.Level] = recovered[i]
			}
		}
		computed := rootOf(value, slot, proof)
		valid := bytes.Equal(computed, dir.root)
		row["proof_verify_ms"] = ms(part)
		row["serialized_proof_wall_ms"] = ms(start)
		require(valid, "reconstructed root mismatch")
		// All publisher/expected-set/negative/fingerprint diagnostics are untimed.
		for i, pick := range picks {
			if pick.Record >= 0 {
				require(bytes.Equal(recovered[i], raw[pick.Record]), "recovered digest differs from publisher oracle")
			} else {
				require(bytes.Equal(recovered[i], make([]byte, 32)), "empty bucket dummy failed")
			}
		}
		actual := map[Need]bool{}
		for _, x := range needed {
			actual[Need{x.Record, x.Level}] = true
		}
		if target.Needed != nil {
			require(len(actual) == len(target.Needed), "expected route width mismatch")
			for _, n := range target.Needed {
				require(actual[n], "online route differs from expected record/level")
			}
		}
		first := -1
		for level := range levels {
			if first < 0 || level < first {
				first = level
			}
		}
		bad := append([][]byte{}, proof...)
		bad[first] = append([]byte{}, proof[first]...)
		bad[first][0] ^= 1
		flip := !bytes.Equal(rootOf(value, slot, bad), dir.root)
		wrongSlot := append([]byte{}, slot...)
		wrongSlot[len(wrongSlot)-1] ^= 1
		wrongBits := !bytes.Equal(rootOf(value, wrongSlot, proof), dir.root)
		wrongValue := append([]byte{}, value...)
		wrongValue[0] ^= 1
		wrongVal := !bytes.Equal(rootOf(wrongValue, slot, proof), dir.root)
		require(flip && wrongBits && wrongVal, "negative root check failed")
		// On the first excluded warmup (or first measured row if no warmup),
		// compare the official uint64 Recover result to our full record's low64.
		upstreamChecked := ordinal == 0
		if upstreamChecked {
			for i, pick := range picks {
				b := backends[pick.Bucket]
				v := pi.Recover(uint64(pick.Position), 0, b.hint, queries[i], clientAnswers[i], b.clientShared, states[i], b.p, b.clientInfo)
				require(v == binary.BigEndian.Uint64(recovered[i][24:]), "upstream uint64 Recover disagrees with width wrapper")
			}
		}
		for i, q := range queries {
			wire, _ := encode([]pir.Msg{q})
			fingerprint := sha(wire)
			require(!querySeen[fingerprint], "repeated full encrypted query")
			querySeen[fingerprint] = true
			wire, _ = encode([]pir.Msg{pir.MakeMsg(states[i].Data...)})
			fingerprint = sha(wire)
			require(!secretSeen[fingerprint], "repeated private secret")
			secretSeen[fingerprint] = true
		}
		items := []Obj{}
		positions := []int{}
		proofHex := []string{}
		for i, pick := range picks {
			item := Obj{"bucket": pick.Bucket, "query_slot": i, "position": pick.Position, "record": pick.Record, "record_hex": hex.EncodeToString(recovered[i]), "real": pick.Level >= 0}
			if pick.Level >= 0 {
				item["level"] = pick.Level
			}
			items = append(items, item)
			positions = append(positions, pick.Position)
		}
		for _, b := range proof {
			proofHex = append(proofHex, hex.EncodeToString(b))
		}
		row["recovered_by_bucket"] = items
		row["proof_bottom_up_hex"] = proofHex
		row["positions_by_query"] = positions
		row["valid_root"] = valid
		row["computed_root_hex"] = hex.EncodeToString(computed)
		row["corruption_rejected"] = flip
		row["bitflip_rejected"] = flip
		row["wrong_coordinate_rejected"] = wrongBits
		row["wrong_value_rejected"] = wrongVal
		row["real_records"] = len(needed)
		row["dummy_logical_slots"] = len(picks) - len(needed)
		row["PIR_calls"] = len(picks)
		row["query_matrix_payload_bytes"] = qp
		row["query_framed_bytes"] = qf
		row["answer_matrix_payload_bytes"] = ap
		row["answer_framed_bytes"] = af
		row["online_framed_bytes"] = qf + af
		row["upstream_uint64_recover_low64_checked"] = upstreamChecked
		return row
	}
	for w := 0; w < warmup; w++ {
		warmupRows = append(warmupRows, one(in.Targets[w%len(in.Targets)], w, true))
		report["warmups"] = warmupRows
	}
	for i, t := range in.Targets {
		queryRows = append(queryRows, one(t, warmup+i, false))
		report["queries"] = queryRows
	}
	report["status"] = "passed"
	report["proofs_verified"] = len(queryRows)
	report["warmup_proofs_verified"] = len(warmupRows)
	report["all_encrypted_queries_distinct"] = true
	report["all_private_secrets_distinct"] = true
	return 0
}
func main() {
	if len(os.Args) != 4 {
		fmt.Fprintln(os.Stderr, "usage: simplepir_proof_bench INPUT_JSON OUTPUT_JSON WARMUP_COUNT")
		os.Exit(2)
	}
	count, e := strconv.Atoi(os.Args[3])
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(2)
	}
	runtime.GOMAXPROCS(1)
	debug.SetMemoryLimit(8 * 1024 * 1024 * 1024)
	must(os.Setenv("OMP_NUM_THREADS", "1"))
	os.Stdout = os.Stderr // upstream parameter logging
	os.Exit(execute(os.Args[1], os.Args[2], count))
}
