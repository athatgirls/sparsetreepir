package main

import (
	"bytes"
	"encoding/binary"
	"testing"

	"github.com/ahenzinger/simplepir/pir"
)

// Untimed correctness tests of the only widened cryptographic API boundary.
func TestLongRecordBoundaryAndRoundtrip(t *testing.T) {
	pi := pir.SimplePIR{}
	records := make([][]byte, 33)
	for i := range records {
		records[i] = make([]byte, 32)
		for j := range records[i] {
			records[i][j] = byte(i*31 + j)
		}
	}
	records[0] = make([]byte, 32)
	records[1] = bytes.Repeat([]byte{255}, 32)
	records[2] = make([]byte, 32)
	records[2][0] = 128
	records[3] = make([]byte, 32)
	records[3][31] = 1
	p := pi.PickParams(uint64(len(records)), 256, 1024, 32)
	cb := &Backend{p: p, db: make256(records, p)}
	cb.serverShared = pi.Init(cb.db.Info, p)
	loaded, _, _ := roundtrip([]pir.Msg{pir.MakeMsg(cb.serverShared.Data...)})
	cb.clientShared = pir.MakeState(loaded[0].Data...)
	var hint pir.Msg
	cb.server, hint = pi.Setup(cb.db, cb.serverShared, p)
	loaded, _, _ = roundtrip([]pir.Msg{hint})
	cb.hint = loaded[0]
	cb.clientInfo = cb.db.Info
	for _, i := range []int{0, 1, 2, 3, 16, 32, 1} {
		state, q := pi.Query(uint64(i), cb.clientShared, p, cb.clientInfo)
		serverQ, qp, qf := roundtrip([]pir.Msg{q})
		if qf != qp+32 {
			t.Fatal("unexpected singleton frame length")
		}
		ans := pi.Answer(cb.db, pir.MakeMsgSlice(serverQ[0]), cb.server, cb.serverShared, p)
		clientAns, ap, af := roundtrip([]pir.Msg{ans})
		if af != ap+32 {
			t.Fatal("unexpected answer frame length")
		}
		got := recover256(uint64(i), cb, state, q, clientAns[0])
		if !bytes.Equal(got, records[i]) {
			t.Fatalf("record %d mismatch", i)
		}
		low := pi.Recover(uint64(i), 0, cb.hint, q, clientAns[0], cb.clientShared, state, p, cb.clientInfo)
		if low != binary.BigEndian.Uint64(got[24:]) {
			t.Fatalf("official Recover low64 differs at %d", i)
		}
	}
}

func TestCodecFreshStorageAndMultipleMessages(t *testing.T) {
	m := pir.MatrixZeros(2, 3)
	for i := uint64(0); i < 2; i++ {
		for j := uint64(0); j < 3; j++ {
			m.Set((1<<32)-1-i*3-j, i, j)
		}
	}
	loaded, payload, framed := roundtrip([]pir.Msg{pir.MakeMsg(m), pir.MakeMsg(m)})
	if payload != 48 || framed != 104 {
		t.Fatalf("wrong frame counts %d %d", payload, framed)
	}
	if loaded[0].Data[0].Get(1, 2) != m.Get(1, 2) {
		t.Fatal("roundtrip mismatch")
	}
	loaded[0].Data[0].Set(0, 0, 0)
	if m.Get(0, 0) != (1<<32)-1 || loaded[1].Data[0].Get(0, 0) != (1<<32)-1 {
		t.Fatal("decoder aliased source/other message")
	}
}

func TestFrozenParameterRange(t *testing.T) {
	pi := pir.SimplePIR{}
	for _, count := range []uint64{1, 33, 154, 341, 1179, 2379, 9552, 18993, 199998} {
		p := pi.PickParams(count, 256, 1024, 32)
		if p.N != 1024 || p.Logq != 32 || p.P != 991 || p.Sigma != 6.4 || p.M > 8192 || p.L%26 != 0 || p.L*p.M < count*26 {
			t.Fatalf("invalid params for %d: %+v", count, p)
		}
	}
}
