// Bounded engineering exploration of standard long-record SimplePIR, 2026-09-10.
// Build this single file in the pinned upstream module; upstream is unchanged.
// No networking or production security claim. All byte outputs say whether they
// are matrix payload or an actually encoded, but untransported, framed message.
package main

import (
	"bytes"
	crand "crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math"
	"math/big"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/ahenzinger/simplepir/pir"
)

type Sub struct {
	Color   int    `json:"color"`
	Records int    `json:"records"`
	File    string `json:"database_file"`
}
type Manifest struct {
	Method   string `json:"method"`
	Height   int    `json:"height"`
	Metadata string `json:"metadata_file"`
	Slots    string `json:"slots_file"`
	Subs     []Sub  `json:"subdatabases"`
}
type PublicChunk struct {
	Params pir.Params
	Info   pir.DBinfo
}
type PublicColor struct {
	Color   int
	Records int
	Chunks  []PublicChunk
}
type Header struct {
	Schema int
	Method string
	Height int
	Colors []PublicColor
}
type Backend struct {
	P                            pir.Params
	DB                           *pir.Database
	Shared, ClientShared, Server pir.State
	Hint                         pir.Msg
	Seed                         *pir.PRGKey
}
type Variant struct {
	Name         string
	Bits         uint64
	Seeded, Wide bool
	Parts        int
}

var variants = []Variant{
	{"eight32_square_expanded", 32, false, false, 8},
	{"packed256_square_expanded", 256, false, false, 1},
	{"packed256_square_seeded", 256, true, false, 1},
	{"packed256_wide_expanded", 256, false, true, 1},
	{"packed256_wide_seeded", 256, true, true, 1},
}

type Sample struct {
	Index              int      `json:"index"`
	ExpectedHex        string   `json:"expected_hex"`
	RecoveredHex       string   `json:"recovered_hex"`
	Valid              bool     `json:"valid"`
	QueryFingerprint   string   `json:"query_fingerprint"`
	SecretFingerprints []string `json:"secret_state_fingerprints"`
}
type Case struct {
	Variant              string     `json:"variant"`
	Color                int        `json:"color"`
	Records              int        `json:"records"`
	Params               pir.Params `json:"params"`
	Info                 pir.DBinfo `json:"db_info"`
	Parts                int        `json:"scalar_queries_per_record"`
	Hint                 uint64     `json:"hint_matrix_bytes"`
	A                    uint64     `json:"expanded_A_matrix_bytes"`
	SeedBytes            uint64     `json:"public_seed_payload_bytes"`
	Upload               uint64     `json:"query_matrix_bytes"`
	Download             uint64     `json:"answer_matrix_bytes"`
	QueryEncoded         uint64     `json:"query_encoded_matrices_bytes"`
	AnswerEncoded        uint64     `json:"answer_encoded_matrices_bytes"`
	SampleCount          int        `json:"checked_records"`
	Samples              []Sample   `json:"samples"`
	SeedExpansionMatches bool       `json:"seed_expansion_matches"`
	AllQueriesDistinct   bool       `json:"repeated_query_fingerprints_distinct"`
	AllSecretsDistinct   bool       `json:"all_sampled_secret_states_distinct"`
	InputSHA             string     `json:"input_sha256"`
	PpowerCoversBits     bool       `json:"p_power_ne_covers_record_bits"`
	SourceConstraint     string     `json:"parameter_constraint"`
	PublicSeedHex        []string   `json:"public_seed_hex,omitempty"`
	SharedASHA           []string   `json:"shared_A_sha256"`
	ClientASHA           []string   `json:"client_A_sha256"`
}
type Summary struct {
	Method        string `json:"method"`
	Variant       string `json:"variant"`
	Cases         []Case `json:"colors"`
	Q             int    `json:"logical_queries"`
	Calls         int    `json:"PIR_calls_per_proof"`
	Hint          uint64 `json:"hint_matrix_bytes"`
	A             uint64 `json:"expanded_A_matrix_bytes"`
	SeedBytes     uint64 `json:"seed_payload_bytes"`
	MatrixOnline  uint64 `json:"online_matrix_bytes_per_proof"`
	EncodedOnline uint64 `json:"encoded_online_bytes_per_proof"`
	Bootstrap     uint64 `json:"encoded_bootstrap_bytes"`
	Directory     int    `json:"metadata_and_slots_bytes"`
	Checks        int    `json:"checked_records"`
	AllValid      bool   `json:"all_correct"`
	HeaderSHA     string `json:"bootstrap_header_sha256"`
}

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func hash(b []byte) string       { v := sha256.Sum256(b); return hex.EncodeToString(v[:]) }
func u64(w io.Writer, v uint64)  { must(binary.Write(w, binary.BigEndian, v)) }
func blob(w io.Writer, b []byte) { u64(w, uint64(len(b))); _, e := w.Write(b); must(e) }
func putMatrices(w io.Writer, ms []*pir.Matrix) {
	u64(w, uint64(len(ms)))
	for _, m := range ms {
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
func stateBytes(s pir.State) uint64 {
	var n uint64
	for _, m := range s.Data {
		n += m.Size() * 4
	}
	return n
}
func encodedMatrices(msg pir.Msg) uint64 {
	var b bytes.Buffer
	putMatrices(&b, msg.Data)
	return uint64(b.Len())
}
func msgHash(msg pir.Msg) string {
	var b bytes.Buffer
	putMatrices(&b, msg.Data)
	return hash(b.Bytes())
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

// This uses a LOCAL public PRG reader. It never replaces pir's process-global
// secret/error PRG. Do not substitute InitCompressedSeeded/DecompressState here.
func localSeededA(p pir.Params, seed *pir.PRGKey) pir.State {
	r := pir.NewBufPRG(pir.NewPRG(seed))
	a := pir.MatrixNew(p.M, p.N)
	mod := new(big.Int).Lsh(big.NewInt(1), uint(p.Logq))
	for i := uint64(0); i < p.M; i++ {
		for j := uint64(0); j < p.N; j++ {
			a.Set(r.RandInt(mod).Uint64(), i, j)
		}
	}
	return pir.MakeState(a)
}
func make256(raw []byte, p *pir.Params) *pir.Database {
	count := uint64(len(raw) / 32)
	db := pir.SetupDB(count, 256, p)
	if db.Info.Packing != 0 || db.Info.Ne != exactNe(256, p.P) {
		panic("unexpected record decomposition")
	}
	db.Data = pir.MatrixZeros(p.L, p.M)
	base := new(big.Int).SetUint64(p.P)
	for i := uint64(0); i < count; i++ {
		value := new(big.Int).SetBytes(raw[32*i : 32*(i+1)])
		for j := uint64(0); j < db.Info.Ne; j++ {
			digit := new(big.Int)
			value.QuoRem(value, base, digit)
			db.Data.Set(digit.Uint64(), (i/p.M)*db.Info.Ne+j, i%p.M)
		}
		if value.Sign() != 0 {
			panic("insufficient base-p digits")
		}
	}
	db.Data.Sub(p.P / 2)
	return db
}

// Identical offset, denoising and centered-digit correction to upstream Recover;
// only the final base-p reconstruction uses big.Int rather than uint64.
func recover256(index uint64, cb *Backend, state pir.State, query, answer pir.Msg) []byte {
	p := cb.P
	info := cb.DB.Info
	q := uint64(1) << p.Logq
	mask := q - 1
	var offset uint64
	for j := uint64(0); j < p.M; j++ {
		offset += (p.P / 2) * query.Data[0].Get(j, 0)
	}
	offset = q - (offset % q)
	product := pir.MatrixMul(cb.Hint.Data[0], state.Data[0])
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
	if value.BitLen() > 256 {
		panic("decoded record exceeds 256 bits")
	}
	return value.FillBytes(make([]byte, 32))
}
func build(raw []byte, v Variant) []*Backend {
	pi := pir.SimplePIR{}
	N := uint64(len(raw) / 32)
	out := make([]*Backend, 0, v.Parts)
	for part := 0; part < v.Parts; part++ {
		p := pi.PickParams(N, v.Bits, 1024, 32)
		if v.Wide {
			p = pi.PickParamsGivenDimensions(1, N, 1024, 32)
			p.L = exactNe(v.Bits, p.P)
		}
		// Both exploration dimension policies use the unmodified upstream table.
		if p.M > 8192 || p.P != 991 || p.N != 1024 || p.Logq != 32 || p.Sigma != 6.4 {
			panic("small-smoke parameter constraints changed")
		}
		if p.L%exactNe(v.Bits, p.P) != 0 || p.L*p.M < N*exactNe(v.Bits, p.P) {
			panic("invalid database dimensions")
		}
		cb := &Backend{P: p}
		if v.Bits == 256 {
			cb.DB = make256(raw, &cb.P)
		} else {
			values := make([]uint64, N)
			for i := range values {
				values[i] = uint64(binary.LittleEndian.Uint32(raw[32*i+4*part : 32*i+4*part+4]))
			}
			cb.DB = pir.MakeDB(N, 32, &cb.P, values)
		}
		if v.Seeded {
			seed := new(pir.PRGKey)
			_, e := io.ReadFull(crand.Reader, seed[:])
			must(e)
			cb.Seed = seed
			cb.Shared = localSeededA(cb.P, seed)
			cb.ClientShared = localSeededA(cb.P, seed)
			if !bytes.Equal([]byte(msgHash(pir.MakeMsg(cb.Shared.Data...))), []byte(msgHash(pir.MakeMsg(cb.ClientShared.Data...)))) {
				panic("public seed expansion differs")
			}
		} else {
			cb.Shared = pi.Init(cb.DB.Info, cb.P)
			cb.ClientShared = cb.Shared
		}
		cb.Server, cb.Hint = pi.Setup(cb.DB, cb.Shared, cb.P)
		out = append(out, cb)
	}
	return out
}
func runColor(sub Sub, raw []byte, v Variant) (Case, PublicColor, []byte) {
	if len(raw) != sub.Records*32 || sub.Records < 1 {
		panic("invalid input records")
	}
	backends := build(raw, v)
	pi := pir.SimplePIR{}
	c := Case{Variant: v.Name, Color: sub.Color, Records: sub.Records, Params: backends[0].P, Info: backends[0].DB.Info, Parts: v.Parts, InputSHA: hash(raw), SeedExpansionMatches: true, PpowerCoversBits: true, SourceConstraint: "Unmodified upstream params.csv row: n=1024, M<=8192, logq=32, sigma=6.4, p=991; squishing basis=10/factor=3; L multiple of Ne and L*M>=records*Ne"}
	pub := PublicColor{Color: sub.Color, Records: sub.Records}
	var boot bytes.Buffer
	for _, cb := range backends {
		pub.Chunks = append(pub.Chunks, PublicChunk{Params: cb.P, Info: cb.DB.Info})
		c.Hint += cb.Hint.Size() * 4
		c.A += stateBytes(cb.Shared)
		c.SharedASHA = append(c.SharedASHA, msgHash(pir.MakeMsg(cb.Shared.Data...)))
		c.ClientASHA = append(c.ClientASHA, msgHash(pir.MakeMsg(cb.ClientShared.Data...)))
		if v.Seeded {
			c.SeedBytes += 16
			c.PublicSeedHex = append(c.PublicSeedHex, hex.EncodeToString(cb.Seed[:]))
			blob(&boot, cb.Seed[:])
		} else {
			putMatrices(&boot, cb.Shared.Data)
		}
		putMatrices(&boot, cb.Hint.Data)
	}
	seen, secretSeen := map[string]bool{}, map[string]bool{}
	selectionHash := sha256.Sum256(raw)
	randomIndex := int(binary.LittleEndian.Uint64(selectionHash[:8]) % uint64(sub.Records))
	for _, index := range []int{0, sub.Records / 2, sub.Records - 1, randomIndex, 0} {
		recovered := make([]byte, 32)
		var fingerprints bytes.Buffer
		var secretFingerprints []string
		var up, down, ue, de uint64
		for part, cb := range backends {
			state, query := pi.Query(uint64(index), cb.ClientShared, cb.P, cb.DB.Info)
			secretHash := msgHash(pir.MakeMsg(state.Data...))
			if secretSeen[secretHash] {
				panic("repeated private secret state")
			}
			secretSeen[secretHash] = true
			secretFingerprints = append(secretFingerprints, secretHash)
			answer := pi.Answer(cb.DB, pir.MakeMsgSlice(query), cb.Server, cb.Shared, cb.P)
			up += query.Size() * 4
			down += answer.Size() * 4
			ue += encodedMatrices(query)
			de += encodedMatrices(answer)
			fingerprints.WriteString(msgHash(query))
			if v.Bits == 256 {
				recovered = recover256(uint64(index), cb, state, query, answer)
			} else {
				value := pi.Recover(uint64(index), 0, cb.Hint, query, answer, cb.ClientShared, state, cb.P, cb.DB.Info)
				binary.LittleEndian.PutUint32(recovered[part*4:part*4+4], uint32(value))
			}
		}
		if c.SampleCount > 0 && (up != c.Upload || down != c.Download || ue != c.QueryEncoded || de != c.AnswerEncoded) {
			panic("variable message shape")
		}
		c.Upload, c.Download, c.QueryEncoded, c.AnswerEncoded = up, down, ue, de
		fingerprint := hash(fingerprints.Bytes())
		if seen[fingerprint] {
			panic("repeated complete query bytes")
		}
		seen[fingerprint] = true
		valid := bytes.Equal(recovered, raw[index*32:(index+1)*32])
		if !valid {
			panic(fmt.Sprintf("record recovery failed %s color=%d index=%d", v.Name, sub.Color, index))
		}
		c.Samples = append(c.Samples, Sample{Index: index, ExpectedHex: hex.EncodeToString(raw[index*32 : (index+1)*32]), RecoveredHex: hex.EncodeToString(recovered), Valid: valid, QueryFingerprint: fingerprint, SecretFingerprints: secretFingerprints})
		c.SampleCount++
	}
	c.AllQueriesDistinct = true
	c.AllSecretsDistinct = true
	return c, pub, boot.Bytes()
}
func runManifest(base string, m Manifest, v Variant) Summary {
	s := Summary{Method: m.Method, Variant: v.Name, Q: len(m.Subs), Calls: len(m.Subs) * v.Parts, AllValid: true}
	header := Header{Schema: 1, Method: m.Method, Height: m.Height}
	if v.Bits == 256 {
		header.Schema = 2
	}
	meta, e := os.ReadFile(filepath.Join(base, m.Metadata))
	must(e)
	slots, e := os.ReadFile(filepath.Join(base, m.Slots))
	must(e)
	s.Directory = len(meta) + len(slots)
	var body bytes.Buffer
	for _, sub := range m.Subs {
		raw, e := os.ReadFile(filepath.Join(base, sub.File))
		must(e)
		c, pub, b := runColor(sub, raw, v)
		s.Cases = append(s.Cases, c)
		header.Colors = append(header.Colors, pub)
		body.Write(b)
		s.Hint += c.Hint
		s.A += c.A
		s.SeedBytes += c.SeedBytes
		s.MatrixOnline += c.Upload + c.Download
		s.EncodedOnline += c.QueryEncoded + c.AnswerEncoded
		s.Checks += c.SampleCount
	}
	s.EncodedOnline += 32 // two uint64 outer frames and two uint64 batch counts
	headerJSON, e := json.Marshal(header)
	must(e)
	var boot bytes.Buffer
	blob(&boot, headerJSON)
	blob(&boot, meta)
	blob(&boot, slots)
	boot.Write(body.Bytes())
	s.Bootstrap = 15 + 8 + uint64(boot.Len())
	s.HeaderSHA = hash(headerJSON)
	return s
}
func main() {
	source := flag.String("source", "", "existing CT publisher directory (read-only)")
	output := flag.String("output", "", "new output JSON")
	flag.Parse()
	if *source == "" || *output == "" {
		panic("source and output required")
	}
	runtime.GOMAXPROCS(1)
	os.Stdout = os.Stderr
	start := time.Now()
	var summaries []Summary
	for _, method := range []string{"first_fit", "activebalance", "nonempty_depth"} {
		base := filepath.Join(*source, method)
		raw, e := os.ReadFile(filepath.Join(base, "server_manifest.json"))
		must(e)
		var m Manifest
		must(json.Unmarshal(raw, &m))
		for _, v := range variants {
			summaries = append(summaries, runManifest(base, m, v))
			runtime.GC()
		}
	}
	// Boundary values exercise all 256 bits and padded final rows; this is not a
	// workload or timing result. Index 0 is zero, last is all ones.
	var synthetic []Case
	for _, count := range []int{1, 33} {
		raw := make([]byte, 32*count)
		for i := 1; i < count; i++ {
			h := sha256.Sum256([]byte(fmt.Sprintf("synthetic-%d", i)))
			copy(raw[32*i:32*(i+1)], h[:])
		}
		for j := 0; j < 32; j++ {
			raw[len(raw)-32+j] = 255
		}
		for _, v := range variants {
			c, _, _ := runColor(Sub{Color: 1, Records: count}, raw, v)
			synthetic = append(synthetic, c)
		}
	}
	result := map[string]any{"schema": 1, "scope": "Bounded engineering smoke on existing real 32-byte CT-derived records; no networking, no SMT proof verification, no publishable performance comparison. Stored records are checked byte-for-byte.", "byte_accounting": "Matrix bytes count uint32 elements. Encoded online/bootstrap sizes are actual bytes.Buffer serialization using the existing TCP framing, but were not transported. Packed Schema 2 and its local-seed field need a matching client implementation; no claim of binary compatibility with the current TCP client.", "security_scope": "Standard vertical long-record representation with unchanged upstream LWE table. Explicit local public-seed expansion never resets the private global query PRG; repeated-query fingerprints are only a sanity check, not a proof of cryptographic security.", "go": runtime.Version(), "gomaxprocs": 1, "source_directory": *source, "summaries": summaries, "synthetic_boundary_checks": synthetic, "wall_seconds_diagnostic_only": time.Since(start).Seconds(), "native_uint64_API_limit": "MakeDB takes []uint64 and Recover returns uint64; Row_length=256 alone does not lift that limit. This helper uses SetupDB and big.Int base-p digit encoding/recovery.", "long_record_digits": uint64(math.Ceil(256 / math.Log2(991))), "standard_optimization_not_new_theory": true}
	b, e := json.MarshalIndent(result, "", "  ")
	must(e)
	must(os.WriteFile(*output, append(b, '\n'), 0644))
}
