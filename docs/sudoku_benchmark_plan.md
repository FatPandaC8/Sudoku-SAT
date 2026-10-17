# Kế hoạch triển khai: Empirical Comparison of SAT Solving and Other Exact Methods for Sudoku

> Môn: Các vấn đề hiện đại KHMT, BTL số 1 (cá nhân).
> Trạng thái: **KẾ HOẠCH, chưa triển khai gì**. Dataset đã cố định (mục 1).
> Mọi thông tin về repo, solver, license đều là **giả định cần xác minh ở Giai đoạn 0**. Các con số kích thước là **tính lý thuyết**, không phải đo thực tế.

---

## 0. Quy tắc cho agent

1. Không tuyên bố solver, encoding hay license khả dụng khi chưa có bằng chứng (import, version, chạy thử).
2. Không thay encoding bằng bản khác dưới cùng tên.
3. Không loại instance khó sau khi xem kết quả, trừ khi có luật khai báo trước (mục 6).
4. Quyết định ảnh hưởng tính hợp lệ thực nghiệm phải hỏi người dùng, không tự chọn.
5. Giai đoạn 0 chỉ đọc môi trường. Không cài gói, không sửa file, không commit/push nếu chưa được yêu cầu.
6. Sau mỗi giai đoạn: chạy pytest, báo kết quả, **dừng chờ duyệt** rồi mới sang giai đoạn kế.
7. Không chạy benchmark đầy đủ trước khi pilot được người dùng xác nhận.

---

## 1. Dataset (CỐ ĐỊNH, không đổi)

| Tham số | Giá trị |
|---|---|
| Kích thước | 9×9 (box 3×3), 36×36 (box 6×6), 81×81 (box 9×9) |
| Tỉ lệ xóa | 0.3, 0.5, 0.7, 0.9 (cả ba kích thước) |
| Số puzzle | 100 / cặp (size, ratio), 12 cặp, **tổng 1.200** |
| Seed gốc | `42`, seed từng puzzle suy ra xác định |
| Nghiệm duy nhất | Không yêu cầu; nghiệm hợp lệ bất kỳ là thành công |

Quy tắc đi kèm:

- Số ô xóa = `round(ratio × N²)`; lưu cả ratio yêu cầu và ratio thực tế.
- Seed per-puzzle: hàm băm ổn định (ví dụ SHA-256 của `"42|N|ratio|index"`). **Không dùng `hash()` của Python** (không xác định giữa các lần chạy).
- ID ổn định, ví dụ `sudoku_N081_r0.7_i042`.
- Metadata: ID, N, kích thước box, ratio yêu cầu/thực tế, seed, phiên bản generator, clues, nghiệm tham chiếu, hash nội dung.
- Sinh lưới đầy đủ bằng mẫu cơ sở `(r·n + r//n + c) mod N`, sau đó hoán vị ký hiệu, xáo hàng/cột trong band/stack, xáo band/stack. Luôn hợp lệ nhưng **không phân phối đều trên mọi lưới Sudoku** (ghi vào Limitations).
- Mọi solver đọc **cùng một file dataset/manifest**, không sinh lại.
- Ratio là biến thực nghiệm, **không phải nhãn độ khó**.

---

## 2. Tóm tắt thiết kế thí nghiệm (đề xuất: Option A, staged)

1. **Stage 1**: so sánh các AMO encoding với **một backend SAT cố định**.
2. **Stage 2**: so sánh các backend SAT với **một encoding cố định**.
3. **Stage 3**: so sánh cấu hình SAT đại diện với 4 solver phi-SAT: CPLEX CP, CPLEX MIP, Gurobi MIP, OR-Tools CP-SAT.

Không chọn Option B (full factorial) vì thêm khoảng 24.000 run mà đề không đòi hỏi.

**Tránh thiên lệch chọn cấu hình**: chia theo chỉ số puzzle trong mỗi cặp.

- Index 0–19 → **tập chọn lọc** (240 puzzle): dùng để chọn encoding/backend đại diện theo luật khai báo trước.
- Index 20–99 → **tập đánh giá** (960 puzzle): báo cáo so sánh SAT vs non-SAT.
- Nếu người dùng muốn báo cáo trên toàn bộ 1.200, phải ghi rõ thiên lệch chọn cấu hình.

Phân loại đúng solver trong báo cáo:

- CPLEX CP: constraint programming.
- CPLEX MIP và Gurobi: MIP/ILP (Gurobi **không** phải CP).
- CP-SAT: solver lai (SAT + lập luận số nguyên), không phải CP thuần.

---

## 3. Các giai đoạn

### Giai đoạn 0: Setup môi trường (chỉ đọc, chưa sửa gì)

| Task | Mục đích / hành vi | File ảnh hưởng | Phụ thuộc | Nghiệm thu | Rủi ro chính |
|---|---|---|---|---|---|
| 0.1 Kiểm tra repo | Liệt kê cấu trúc, mã tái dùng, test, cấu hình, phiên bản Python | không | không | Bảng hiện trạng: đường dẫn + bằng chứng | Repo trống hoặc lệch hướng |
| 0.2 Kiểm tra SAT | PySAT (version), solver trong `pysat.solvers`, `EncType` trong `pysat.card`; kissat/cryptominisat có/không (binary, `--version`) | không | 0.1 | Bảng: có / thiếu / chỉ qua CLI + version | Giả định sai về API |
| 0.3 Kiểm tra non-SAT | `cplex`, `docplex`, binary `cpoptimizer`, `gurobipy`, `ortools`: import, version, license | không | 0.1 | Mỗi solver: khả dụng / giới hạn / bị chặn | Community edition |
| 0.4 Thử ngưỡng license | Dựng thử model nhỏ để xác định kích thước tối đa mỗi solver chạy được | script tạm ngoài repo, hoặc chỉ lệnh đọc | 0.3 | Biết N nào còn chạy được | Phát hiện muộn |
| 0.5 Khóa môi trường | Ghi OS/CPU/RAM, công cụ đo RSS, pin phiên bản | `requirements.txt` / lock, `ENVIRONMENT.md` (sau khi duyệt) | 0.1–0.4 | File ghi môi trường đầy đủ | Môi trường đổi giữa các lần chạy |

**Cổng dừng**: nếu solver thương mại không đủ license cho N=36 hoặc N=81, dừng và hỏi người dùng (mục 10).

### Giai đoạn 1: Generator và dataset

| Task | Mục đích / hành vi | File dự kiến | Phụ thuộc | Nghiệm thu | Rủi ro chính |
|---|---|---|---|---|---|
| 1.1 Validator | Kiểm tra lưới đầy đủ, puzzle (clue khớp nghiệm), nghiệm solver trả về | `src/sudoku/validator.py` | G0 | Test trên lưới nhỏ, gồm mẫu sai (trùng hàng/cột/box, sai clue) | Lỗi biên ở N lớn |
| 1.2 Generator | Lưới hợp lệ → xóa ngẫu nhiên → lưu | `src/sudoku/generator.py` | 1.1 | Cùng seed → byte-identical; 1.200 puzzle qua validator | Thiên lệch cấu trúc lưới (ghi nhận) |
| 1.3 Manifest | Ghi ID, seed, ratio, version, hash, đường dẫn | `data/manifest.csv`, `data/puzzles/*.json(l)` | 1.2 | Hash ổn định giữa 2 lần sinh | Dung lượng (nhỏ, N=81 chỉ 6.561 ô) |
| 1.4 Config + CLI | YAML cho dataset; lệnh sinh dataset | `configs/dataset.yaml`, `scripts/generate_dataset.py` | 1.2 | Một lệnh sinh đủ 1.200 puzzle | Thấp |
| 1.5 Test | Tính xác định, ratio thực tế, ID duy nhất | `tests/test_generator.py`, `tests/test_validator.py` | 1.1–1.4 | pytest xanh | Thấp |

**Cổng dừng**: báo cáo thống kê dataset (số puzzle, ratio thực tế, hash), chờ duyệt.

### Giai đoạn 2: Các nhóm benchmark

#### 2A. Hạ tầng chung

- Adapter chung: `solve(puzzle, timeout) -> Result`.
- Mỗi run chạy trong **subprocess riêng**: đo peak RSS và áp timeout cứng.
- Trạng thái tách biệt: `SOLVED_VALID`, `UNSAT_INVESTIGATE`, `TIMEOUT`, `BUILD_FAIL`, `SOLVER_ERROR`, `INVALID_SOLUTION`, `BLOCKED_LICENSE`.
- UNSAT (puzzle luôn SAT) phải **dừng và điều tra**, không tính là kết quả thường.
- Mọi nghiệm trả về đều được validator độc lập kiểm tra.
- Ghi JSONL từng run: `t_build`, `t_init`, `t_solve`, `t_extract_validate`, `t_total`, `peak_rss`, thống kê riêng solver, version solver.
- Quy ước thời gian: **primary = solve-only**; build tách riêng; nêu rõ chênh lệch giữa các API (PySAT nạp clause trực tiếp, docplex/gurobi có bước tạo model).

| Task | File dự kiến | Nghiệm thu |
|---|---|---|
| 2A.1 Interface + Result schema | `src/bench/base.py` | Test với solver giả (mock) |
| 2A.2 Runner subprocess + RSS + timeout | `src/bench/runner.py` | Test timeout, crash, đo RSS trên tác vụ mẫu |
| 2A.3 Ghi kết quả JSONL/CSV | `src/bench/results.py` | Schema ổn định, đọc lại được |
| 2A.4 Config benchmark YAML | `configs/benchmark.yaml` | Chọn solver/encoding/tập instance qua config |

#### 2B. Nhóm SAT

- Biến one-hot `x[r][c][v]`, số biến chính `N³`.
- Bốn nhóm exactly-one: cell, row/value, col/value, box/value (tổng `4N²` nhóm).
- ALO giữ nguyên (một clause dài mỗi nhóm); **chỉ đổi AMO**, áp đồng nhất cho cả 4 nhóm.
- Clue thêm bằng unit clause, **không tiền xử lý** làm đổi CNF giữa các encoding.
- 5 AMO: pairwise, sequential counter, commander, binary, product.
  - Theo hiểu biết hiện tại, `pysat.card` có pairwise, seqcounter, bitwise (tương ứng "binary"); **commander và product có thể phải tự cài**. Phải xác minh ở 0.2.
  - Phải **định nghĩa chính xác** "binary" và "product" dùng (kèm tham chiếu), không dùng tên mơ hồ.
  - Tự cài thì test vét cạn trên nhóm n ≤ 6–8: tập nghiệm projected lên biến chính đúng bằng "tối đa một biến true".
- Backend: chỉ những gì xác minh được (ví dụ CaDiCaL, Glucose qua PySAT). Kissat/CryptoMiniSat chỉ đưa vào nếu có (qua CLI cần: ghi DIMACS, timeout, parse SAT/UNSAT/UNKNOWN, trích model, validate).
- ALO encoding khác: thí nghiệm riêng, chỉ làm nếu còn thời gian và được duyệt.
- Sinh clause **theo luồng** để tránh giữ hàng chục triệu clause trong list Python ở N=81.

| Task | File dự kiến | Nghiệm thu |
|---|---|---|
| 2B.1 AMO encodings (gọi PySAT hoặc tự cài) | `src/sat/encodings.py` | Test vét cạn, đếm biến/clause khớp công thức |
| 2B.2 CNF builder Sudoku | `src/sat/cnf_builder.py` | CNF + clue SAT, nghiệm decode hợp lệ ở N=9 |
| 2B.3 Adapter SAT (PySAT) | `src/solvers/sat_pysat.py` | Giải được puzzle N=9 mọi encoding; nghiệm qua validator |
| 2B.4 Adapter CLI (nếu có kissat/cms) | `src/solvers/sat_cli.py` | Test parse kết quả, timeout, lỗi |

#### 2C. Nhóm non-SAT

| Solver | API | Mô hình |
|---|---|---|
| CPLEX CP | `docplex.cp` (cần `cpoptimizer`) | Biến nguyên N² miền 1..N, `all_diff` cho hàng/cột/box, clue cố định |
| CPLEX MIP | `docplex.mp` | Nhị phân N³, exactly-one 4 nhóm, clue cố định |
| Gurobi MIP | `gurobipy` | Cùng công thức nhị phân với CPLEX MIP |
| OR-Tools CP-SAT | `ortools.sat.python.cp_model` | Chọn một công thức và ghi rõ (nguyên + `AddAllDifferent`, hoặc nhị phân) |
| Backtracking MRV + forward checking | Python thuần | Tùy chọn, chỉ là baseline |

Cho mỗi solver: định nghĩa tham số (timeout 30s, số thread cố định và giống nhau), trích nghiệm, validate, ghi thống kê riêng (conflicts, nodes, branches... **không coi là tương đương**).

| Task | File dự kiến | Nghiệm thu |
|---|---|---|
| 2C.1 Adapter CPLEX CP | `src/solvers/cplex_cp.py` | Giải N=9 hợp lệ hoặc báo blocker rõ ràng |
| 2C.2 Adapter CPLEX MIP | `src/solvers/cplex_mip.py` | Như trên |
| 2C.3 Adapter Gurobi | `src/solvers/gurobi_mip.py` | Như trên |
| 2C.4 Adapter CP-SAT | `src/solvers/ortools_cpsat.py` | Như trên |
| 2C.5 Xử lý solver không khả dụng | `src/bench/availability.py` | Trả `BLOCKED_LICENSE`/`UNAVAILABLE`, không bỏ lặng lẽ, kèm fallback gắn nhãn |
| 2C.6 (tùy chọn) Backtracking | `src/solvers/backtracking.py` | Giải N=9, ghi nhãn "baseline" |

Test chéo: mọi solver giải cùng tập puzzle N=9 nhỏ, mọi nghiệm qua validator.

#### 2D. Pilot (xem mục 6)

#### 2E. Chạy đầy đủ (chỉ sau khi pilot được duyệt)

### Giai đoạn 3: Phân tích

Script: `scripts/analyze.py` (đọc JSONL, xuất bảng và hình).

- Median runtime theo nhóm (solver × size × ratio).
- Solved rate, timeout rate.
- Cactus plot.
- Runtime theo size và ratio; phân tích scaling.
- Peak RSS.
- CNF size theo encoding (biến, clause, literal).
- Thống kê tìm kiếm riêng từng solver.
- Với 1 run/instance: **không khẳng định đã đo biến thiên giữa các lần chạy**.
- Không giả định SAT thắng.

### Giai đoạn 4: Bài báo

- Mẫu của khoa ("Mau xay dung Bao cao BTL so 1 va BTL so 2.pdf") và `\documentclass[a4paper,fleqn]{cas-sc}`.
- Gồm: Methodology, Results, Limitations (generator không đều, license, môi trường, 1 run), Data Availability (link repo).
- Kết luận bám sát số liệu.

---

## 4. Cấu trúc thư mục đề xuất

```
configs/        dataset.yaml, benchmark.yaml
data/           manifest.csv, puzzles/
src/sudoku/     generator.py, validator.py
src/sat/        encodings.py, cnf_builder.py
src/solvers/    sat_pysat.py, sat_cli.py, cplex_cp.py, cplex_mip.py,
                gurobi_mip.py, ortools_cpsat.py, backtracking.py
src/bench/      base.py, runner.py, results.py, availability.py
scripts/        generate_dataset.py, run_pilot.py, run_benchmark.py, analyze.py
tests/          test_generator.py, test_validator.py, test_encodings.py,
                test_sat_solver.py, test_adapters.py, test_runner.py, test_smoke.py
results/        raw/*.jsonl, summary/*.csv, figures/
paper/          main.tex, refs.bib
```

(Tận dụng mã có sẵn nếu repo đã có; chỉ tạo mới khi cần.)

---

## 5. Rủi ro khả thi (tính lý thuyết)

### 5.1 Kích thước SAT (one-hot)

| N | Biến chính (N³) | Số nhóm (4N²) | Clause ALO | AMO pairwise `4N²·C(N,2)` |
|---|---|---|---|---|
| 9 | 729 | 324 | 324 | 11.664 |
| 36 | 46.656 | 5.184 | 5.184 | 3.265.920 |
| 81 | 531.441 | 26.244 | 26.244 | ≈ 85,0 triệu |

Ước lượng cho N=81 (định nghĩa phổ biến, **cần xác minh bằng test đếm**):

| Encoding | Biến phụ | Clause |
|---|---|---|
| Sequential counter | ≈ 2,1 triệu | ≈ 6,3 triệu |
| Binary (bitwise) | ≈ 0,18 triệu | ≈ 14,9 triệu |
| Commander, product | tăng gần tuyến tính theo n | phụ thuộc tham số, phải định nghĩa trước |

### 5.2 Kích thước model non-SAT

- MIP nhị phân: N³ biến = 729 / 46.656 / 531.441.
- CP số nguyên: N² biến = 81 / 1.296 / 6.561.

### 5.3 Rủi ro xếp theo mức ảnh hưởng

| # | Rủi ro | Giảm thiểu |
|---|---|---|
| 1 | **License CPLEX/Gurobi** (lớn nhất): bản community/restricted thường giới hạn cỡ 1.000–2.000 biến hoặc ràng buộc (cần xác minh phiên bản hiện hành). MIP N=36 và N=81 gần như chắc chắn vượt; CP N=81 có thể vượt | Kiểm tra ở G0; nếu bị chặn: ghi "environment blocker", ô trống trong kết quả, fallback gắn nhãn; không bịa số liệu |
| 2 | **Bộ nhớ dựng pairwise N=81** (85 triệu clause trong Python có thể tốn hàng chục GB, ước lượng thô) | Sinh clause theo luồng, hoặc ghi DIMACS; nếu vẫn thất bại ghi `BUILD_FAIL`/resource failure theo luật khai báo trước |
| 3 | **Thời gian dựng model ở N=81** có thể vượt 30s | Timeout 20s chỉ áp cho solve; ngưỡng build riêng (đề xuất 300s, cần duyệt) |
| 4 | **PySAT thiếu commander/product** | Xác minh API; tự cài, định nghĩa rõ, test vét cạn |
| 5 | **Timeout cao ở N=81** (đặc biệt ratio 0.9) | Timeout là kết quả hợp lệ; pilot phát hiện sớm nếu gần như tất cả timeout |
| 6 | **Thiên lệch chọn cấu hình** | Tách tập chọn lọc / tập đánh giá (mục 2) |
| 7 | **Ratio ≠ độ khó** | Không diễn giải ratio như mức độ khó |
| 8 | **Overhead đo RSS bằng subprocess** | Cùng cơ chế cho mọi solver; ghi baseline |
| 9 | **Số thread khác nhau giữa solver** làm méo so sánh | Cố định cùng số thread (hoặc ghi rõ nếu khác) |

---

## 6. Pilot trước khi chạy đầy đủ

- **Phạm vi**: 3 puzzle × 12 cặp = **36 instance** (index cố định 0–2, nằm trong tập chọn lọc).
- **Cấu hình**: tất cả cấu hình dự kiến (khoảng 12: 5 AMO với 1 backend, backend khác với 1 encoding, 4 non-SAT).
- **Số run**: ≈ 36 × 12 = 432; trần 432 phút nếu mọi run timeout (thực tế thấp hơn nhiều).
- **Đo**: build, init, solve, extract+validate, peak RSS, số biến/clause/literal, trạng thái từng run.

**Luật quyết định khai báo trước** (các con số cần người dùng duyệt):

| Tình huống trong pilot | Hành động |
|---|---|
| Cấu hình giải được ≥ 1 puzzle ở mọi cặp | Tiếp tục đủ 100 puzzle/cặp |
| Cấu hình timeout 100% ở một cặp (size, ratio) | Vẫn chạy, nhưng giảm puzzle cho cặp đó (ví dụ 100 → 30 puzzle đầu theo index), ghi lý do |
| Build vượt ngưỡng thời gian/bộ nhớ ở N=81 | Loại cấu hình **cho N=81**, ghi "build infeasible" (không phải solver thất bại) |
| Solver bị chặn bởi license | `BLOCKED_LICENSE`, ghi ô trống, không bịa |
| Bất kỳ kết quả UNSAT | Dừng, điều tra generator/encoding/adapter |
| Nghiệm không qua validator | Ghi `INVALID_SOLUTION`, điều tra adapter |

Việc giảm số puzzle áp theo **chỉ số puzzle** (ví dụ 30 puzzle đầu), cố định trước khi xem kết quả đầy đủ, không chọn theo độ khó quan sát.

---

## 7. Ma trận thí nghiệm và số run (Option A)

Giả sử 5 encoding, 4 backend SAT, 4 non-SAT (số thực tế phụ thuộc Giai đoạn 0):

| Stage | Cấu hình | Instance | Số run |
|---|---|---|---|
| 1. So AMO, 1 backend cố định | 5 encoding | 1.200 | 6.000 |
| 2. So backend, 1 encoding cố định | 3 backend thêm | 1.200 | 3.600 |
| 3. SAT vs non-SAT | 4 non-SAT (SAT đại diện tái dùng run sẵn có) | 1.200 | 4.800 |
| **Tổng** | | | **≈ 14.400** |

- Trần lý thuyết: 14.400 × 30s = 120 giờ (khi mọi run timeout; không thực tế).
- Ước lượng thực chỉ đưa ra **sau pilot**; khi đó đề xuất trần giờ chạy.
- Cắt giảm theo luật: bỏ encoding build-infeasible ở N=81; giảm puzzle theo mục 6; bỏ backend không khả dụng.
- Với 1 run/instance, không báo cáo biến thiên giữa các lần chạy.

---

## 8. Kiểm thử (tổng hợp)

| Nhóm test | Nội dung |
|---|---|
| AMO/ALO | Vét cạn nhóm nhỏ; số biến/clause đúng công thức |
| SAT | CNF + clue SAT; decode nghiệm hợp lệ |
| Validator | Puzzle và nghiệm: mẫu đúng và mẫu sai |
| Adapter | Parse kết quả, phân loại timeout/lỗi, trạng thái solver không khả dụng |
| Cross-solver | Mọi solver giải cùng tập N=9 nhỏ, nghiệm hợp lệ |
| Dataset | Tính xác định, ratio thực tế, ID duy nhất, hash ổn định |
| Smoke | Benchmark mini (vài puzzle N=9) chạy end-to-end ra JSONL + CSV |

---

## 9. Sản phẩm đầu ra mong đợi

- Dataset: `data/manifest.csv`, `data/puzzles/`.
- Raw: `results/raw/*.jsonl` (mỗi run một dòng).
- Tóm tắt: `results/summary/*.csv`.
- Hình: cactus, runtime theo size/ratio, scaling, peak RSS, CNF size.
- Môi trường: `ENVIRONMENT.md`, file pin phiên bản.
- Bài báo: `paper/main.tex` (`cas-sc`), `refs.bib`.
- README: cách tái lập (sinh dataset, chạy pilot, chạy benchmark, phân tích).

---

## 10. Quyết định cần người dùng duyệt (tối thiểu)

| # | Vấn đề                                   | Quyết định đề xuất                                                           |
| - | ---------------------------------------- | ---------------------------------------------------------------------------- |
| 1 | CPLEX/Gurobi không có license phù hợp?   | Kiểm tra trước, báo blocker và chờ duyệt cách xử lý.                         |
| 2 | Giới hạn máy và thời gian chạy?          | Kiểm tra cấu hình thực tế; chưa đặt giới hạn 2 giờ trước pilot.              |
| 3 | Chia dataset để chọn và đánh giá?        | Đồng ý: 20 puzzle chọn cấu hình, 80 puzzle đánh giá trong mỗi nhóm.          |
| 4 | Solver timeout hoặc dựng model thất bại? | Giữ đủ 100 puzzle mỗi nhóm; ghi nhận timeout/failure, không tự giảm dataset. |
| 5 | Số CPU thread mỗi solver?                | Dùng 1 thread nếu solver hỗ trợ.                                             |
Sau khi duyệt, bắt đầu từ Giai đoạn 0 (chỉ đọc môi trường), báo cáo, rồi dừng chờ lệnh sang Giai đoạn 1.
