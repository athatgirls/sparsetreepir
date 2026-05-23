package main

import (
	"flag"
	"fmt"
	"log"
	"math"
	"math/rand"
	"strconv"
	"strings"
	"time"

	"example.com/util"
)

type LocalHint struct {
	key             util.PrfKey
	parity          uint64
	programmedPoint uint64
	isProgrammed    bool
}

type Metrics struct {
	SetupMs    float64
	ClientMs   float64
	ServerMs   float64
	DecodeMs   float64
	UploadKB   float64
	DownloadKB float64
	OfflineKB  float64
	Queries    int
}

func Elem(hint *LocalHint, chunkSize uint64, chunkId uint64) uint64 {
	if hint.isProgrammed && chunkId == hint.programmedPoint/chunkSize {
		return hint.programmedPoint
	}
	return util.PRFEval(&hint.key, chunkId)%chunkSize + chunkId*chunkSize
}

func parseSizes(raw string) []uint64 {
	parts := strings.Split(raw, ",")
	sizes := make([]uint64, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		value, err := strconv.ParseUint(part, 10, 64)
		if err != nil {
			log.Fatalf("bad size %q: %v", part, err)
		}
		if value == 0 {
			value = 1
		}
		sizes = append(sizes, value)
	}
	if len(sizes) == 0 {
		log.Fatalf("no sizes provided")
	}
	return sizes
}

func runOne(dbSize uint64, queryCount int, seed int64) Metrics {
	if dbSize < 2 {
		dbSize = 2
	}
	rng := rand.New(rand.NewSource(seed))
	db := make([]uint64, dbSize)
	for i := uint64(0); i < dbSize; i++ {
		db[i] = rng.Uint64()
	}
	chunkSize := uint64(math.Sqrt(float64(dbSize)))
	if chunkSize < 1 {
		chunkSize = 1
	}
	chunkNum := uint64(math.Ceil(float64(dbSize) / float64(chunkSize)))
	qWindow := uint64(math.Sqrt(float64(dbSize)) * math.Log(float64(dbSize)))
	if qWindow < 1 {
		qWindow = 1
	}
	m1 := 4 * uint64(math.Sqrt(float64(dbSize))*math.Log(float64(dbSize)))
	if m1 < chunkSize {
		m1 = chunkSize
	}
	m2 := 4 * uint64(math.Log(float64(dbSize)))
	if m2 < 2 {
		m2 = 2
	}
	if uint64(queryCount) > qWindow {
		queryCount = int(qWindow)
	}
	if queryCount < 1 {
		queryCount = 1
	}
	primaryHints := make([]LocalHint, m1)
	replacementIndices := make([]uint64, m2*chunkNum)
	replacementValues := make([]uint64, m2*chunkNum)
	backupHints := make([]LocalHint, m2*chunkNum)
	for i := uint64(0); i < m1; i++ {
		primaryHints[i] = LocalHint{key: util.RandKey(rng)}
	}
	for i := uint64(0); i < m2*chunkNum; i++ {
		backupHints[i] = LocalHint{key: util.RandKey(rng)}
	}
	setupStart := time.Now()
	for i := uint64(0); i < chunkNum; i++ {
		for j := uint64(0); j < m1; j++ {
			idx := Elem(&primaryHints[j], chunkSize, i)
			if idx >= dbSize {
				idx = dbSize - 1
			}
			primaryHints[j].parity ^= db[idx]
		}
		for j := uint64(0); j < m2*chunkNum; j++ {
			if j/m2 != i {
				idx := Elem(&backupHints[j], chunkSize, i)
				if idx >= dbSize {
					idx = dbSize - 1
				}
				backupHints[j].parity ^= db[idx]
			}
		}
		for j := i * m2; j < (i+1)*m2; j++ {
			ind := rng.Uint64()%chunkSize + i*chunkSize
			if ind >= dbSize {
				ind = dbSize - 1
			}
			replacementIndices[j] = ind
			replacementValues[j] = db[ind]
		}
	}
	setupMs := float64(time.Since(setupStart).Microseconds()) / 1000.0
	localCache := make(map[uint64]uint64)
	consumedReplacementNum := make([]uint64, chunkNum)
	consumedHintNum := make([]uint64, chunkNum)
	var clientMs, serverMs, decodeMs float64
	completed := 0
	for q := 0; q < queryCount; q++ {
		x := rng.Uint64() % dbSize
		for {
			if _, ok := localCache[x]; !ok {
				break
			}
			x = rng.Uint64() % dbSize
		}
		chunkId := x / chunkSize
		if chunkId >= chunkNum {
			chunkId = chunkNum - 1
		}
		c0 := time.Now()
		hitId := uint64(math.MaxUint64)
		for i := uint64(0); i < m1; i++ {
			if Elem(&primaryHints[i], chunkSize, chunkId) == x {
				hitId = i
				break
			}
		}
		if hitId == uint64(math.MaxUint64) {
			continue
		}
		expandedSet := make([]uint64, chunkNum)
		for i := uint64(0); i < chunkNum; i++ {
			idx := Elem(&primaryHints[hitId], chunkSize, i)
			if idx >= dbSize {
				idx = dbSize - 1
			}
			expandedSet[i] = idx
		}
		if consumedReplacementNum[chunkId] >= m2 {
			break
		}
		tmp := consumedReplacementNum[chunkId] + chunkId*m2
		replacementInd := replacementIndices[tmp]
		replacementVal := replacementValues[tmp]
		consumedReplacementNum[chunkId]++
		expandedSet[chunkId] = replacementInd
		clientMs += float64(time.Since(c0).Microseconds()) / 1000.0
		s0 := time.Now()
		parity := uint64(0)
		for _, index := range expandedSet {
			parity ^= db[index]
		}
		serverMs += float64(time.Since(s0).Microseconds()) / 1000.0
		d0 := time.Now()
		answer := parity ^ primaryHints[hitId].parity ^ replacementVal
		if answer != db[x] {
			log.Fatalf("decode failed")
		}
		localCache[x] = answer
		if consumedHintNum[chunkId] >= m2 {
			break
		}
		primaryHints[hitId] = backupHints[chunkId*m2+consumedHintNum[chunkId]]
		primaryHints[hitId].isProgrammed = true
		primaryHints[hitId].programmedPoint = x
		primaryHints[hitId].parity ^= answer
		consumedHintNum[chunkId]++
		decodeMs += float64(time.Since(d0).Microseconds()) / 1000.0
		completed++
	}
	perQueryUpload := float64(chunkNum*8) / 1024.0
	perQueryDownload := float64(8) / 1024.0
	offline := float64((m1 + m2*chunkNum) * 24) / 1024.0
	return Metrics{setupMs, clientMs, serverMs, decodeMs, perQueryUpload * float64(completed), perQueryDownload * float64(completed), offline, completed}
}

func main() {
	sizesRaw := flag.String("sizes", "100", "comma-separated DB sizes")
	queries := flag.Int("queries", 20, "queries per subdatabase")
	seed := flag.Int64("seed", 1, "seed")
	flag.Parse()
	sizes := parseSizes(*sizesRaw)
	total := Metrics{}
	for i, size := range sizes {
		m := runOne(size, *queries, *seed+int64(i)*7919)
		total.SetupMs += m.SetupMs
		total.ClientMs += m.ClientMs
		total.ServerMs += m.ServerMs
		if m.ServerMs > total.DecodeMs {
			total.DecodeMs = m.ServerMs
		}
		total.UploadKB += m.UploadKB
		total.DownloadKB += m.DownloadKB
		total.OfflineKB += m.OfflineKB
		total.Queries += m.Queries
	}
	fmt.Printf("setup_ms,client_query_ms,server_total_ms,server_parallel_ms,online_upload_kb,online_download_kb,online_total_kb,offline_kb,queries\n")
	fmt.Printf("%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%d\n", total.SetupMs, total.ClientMs, total.ServerMs, total.DecodeMs, total.UploadKB, total.DownloadKB, total.UploadKB+total.DownloadKB, total.OfflineKB, total.Queries)
}
