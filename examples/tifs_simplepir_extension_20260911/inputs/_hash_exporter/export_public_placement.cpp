// Public-placement exporter; official utility included unchanged.
#include <algorithm>
#include <fstream>
#include <functional>
#include <string>
#include "src/utils.h"
int main(int argc, char** argv) {
  if (argc != 4) return 2;
  const size_t n = std::stoull(argv[1]), b = std::stoull(argv[2]);
  if (b < 3) return 3;
  std::ofstream out(argv[3]);
  for (size_t r = 0; r < n; ++r) {
    const auto candidates = utils::get_candidate_buckets(r, 3, b);
    out << r;
    for (auto c : candidates) out << '\t' << c;
    out << '\n';
  }
  return out ? 0 : 4;
}
