# Cấu trúc dự án Vietnamese Legal RAG

## Mục đích và cách dùng tài liệu

Tài liệu này ghi cấu trúc MVP đã thống nhất, trách nhiệm từng file, luồng dữ liệu và thứ tự triển khai. Đọc cùng [PROJECT_PLAN.md](PROJECT_PLAN.md), nơi lưu mục tiêu, phạm vi và các giai đoạn của project.

Đây là cấu trúc đích, không phải danh sách file đã được triển khai. Chỉ tạo từng file khi đến bước cần dùng, giải thích đầu vào/đầu ra và kiểm tra trước khi chuyển bước. Khi thay đổi kiến trúc, cập nhật tài liệu tương ứng để những lần làm việc tiếp theo có thể tiếp tục từ quyết định hiện tại.

## 1. Phạm vi đã thống nhất

- Dùng dataset `th1nhng0/vietnamese-legal-documents`, khóa revision và tải đầy đủ ba phần hiện hành: `metadata`, `content`, `relationships`. Không tải các config legacy cho MVP.
- Ban đầu chỉ chọn 200 văn bản hợp lệ để làm sạch, chia chunk, embedding và lập chỉ mục. Ghép metadata với content theo `id`, không lấy độc lập 200 dòng ở từng bảng.
- BM25 và dense search dùng cùng một tập chunk; hybrid kết hợp bằng Reciprocal Rank Fusion (RRF).
- Chroma dùng `PersistentClient` lưu trên đĩa. Code chạy bằng lệnh terminal ở local hoặc Kaggle; không phụ thuộc notebook.
- Metadata dùng để ghép dữ liệu, định danh, truy ngược nguồn, đánh giá và hiển thị trích dẫn. MVP chưa tự tạo metadata filter từ câu hỏi.
- Chưa làm graph hoặc agent. Quan hệ văn bản được giữ trong dữ liệu nguồn để có thể nghiên cứu sau.
- Model embedding, LLM và cách phục vụ model cụ thể được chốt khi đến bước đó. Không coi việc dùng vLLM hoặc một model cụ thể là quyết định đã hoàn tất.

## 2. Cây thư mục dự kiến

```text
Vietnamese_Legal_Rag/
├── PROJECT_PLAN.md
├── PROJECT_STRUCTURE.md
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
│
├── configs/
│   ├── project.yaml
│   └── sample_200_ids.json
│
├── src/
│   └── legal_rag/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── schemas.py
│       ├── storage.py
│       │
│       ├── data/
│       │   ├── __init__.py
│       │   ├── download.py
│       │   ├── sample.py
│       │   ├── clean.py
│       │   └── chunk.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── embedding.py
│       │   └── llm.py
│       │
│       ├── retrieval/
│       │   ├── __init__.py
│       │   ├── bm25.py
│       │   ├── dense.py
│       │   └── hybrid.py
│       │
│       ├── generation/
│       │   ├── __init__.py
│       │   ├── answer.py
│       │   └── prompt.txt
│       │
│       ├── evaluation/
│       │   ├── __init__.py
│       │   ├── dataset.py
│       │   ├── metrics.py
│       │   └── runner.py
│       │
│       └── app/
│           ├── __init__.py
│           ├── api.py
│           └── ui.py
│
├── data/
│   ├── raw/
│   │   ├── metadata/
│   │   ├── content/
│   │   ├── relationships/
│   │   └── manifest.json
│   │
│   ├── processed/
│   │   └── sample_200/
│   │       ├── documents.jsonl
│   │       ├── cleaned_documents.jsonl
│   │       ├── chunks.jsonl
│   │       └── manifest.json
│   │
│   └── indexes/
│       └── sample_200/
│           ├── bm25.pkl
│           ├── chroma/
│           └── manifest.json
│
├── eval/
│   └── sample_200/
│       └── questions.jsonl
│
├── results/
│   └── <run_id>/
│       ├── config.json
│       ├── retrieval.jsonl
│       ├── metrics.json
│       └── answer_review.jsonl
│
└── tests/
    ├── fixtures/
    ├── test_data_pipeline.py
    ├── test_retrieval.py
    └── test_evaluation.py
```

`<run_id>` đại diện cho mã của một lần đánh giá. Các file trong `data/` và `results/` xuất hiện khi chạy chức năng tương ứng; không tạo file rỗng để lấp đầy cây thư mục. Các file bên trong `chroma/` do Chroma quản lý.

## 3. Tài liệu, cấu hình và môi trường

| File | Trách nhiệm |
|---|---|
| `PROJECT_PLAN.md` | Mục tiêu, phạm vi, các giai đoạn và quyết định đã thống nhất. |
| `PROJECT_STRUCTURE.md` | Cấu trúc đích, trách nhiệm từng file, luồng dữ liệu và thứ tự triển khai. |
| `README.md` | Hướng dẫn cài đặt, chạy từng bước, benchmark, ví dụ và giới hạn của hệ thống. |
| `pyproject.toml` | Khai báo package Python, dependency và cấu hình công cụ phát triển; là nơi khai báo thư viện cần cài ở giai đoạn đầu. |
| `.gitignore` | Bỏ qua môi trường Python, cache, dữ liệu lớn, index và `.env`. |
| `.env.example` | Mẫu tên biến môi trường cho token/API key; không chứa bí mật thật và không mô tả môi trường Conda. |
| `configs/project.yaml` | Dataset, revision, đường dẫn, cấu hình chunking, embedding, retrieval và LLM; bổ sung dần khi đến bước tương ứng. |
| `configs/sample_200_ids.json` | Danh sách 200 ID cố định sau khi chọn mẫu, lưu vào Git để tái lập corpus. |

Dùng môi trường Conda `legal-rag` với Python 3.11 đã tạo ở local. Conda quản lý Python và môi trường; `pyproject.toml` khai báo package và các dependency Python được cài bằng pip bên trong môi trường đó.

Ở giai đoạn đầu, chưa thêm file khai báo môi trường hoặc danh sách dependency riêng bên cạnh `pyproject.toml`. Cách khóa phiên bản để chạy lại trên Kaggle và máy khác sẽ được bổ sung sau khi pipeline đầu tiên chạy được.

URL dịch vụ và đường dẫn lấy từ cấu hình để cùng code có thể chạy ở local và Kaggle. Token/API key lấy từ biến môi trường. Chỉ cài dependency của giai đoạn đang triển khai; môi trường phục vụ model có thể cần tách riêng khi kiểm tra tính tương thích thực tế.

## 4. Trách nhiệm code Python

### Các file dùng chung

| File | Trách nhiệm |
|---|---|
| `cli.py` | Nhận lệnh terminal, đọc tham số, nạp cấu hình và gọi các hàm xử lý tương ứng; chỉ điều phối luồng chạy. |
| `config.py` | Đọc, kiểm tra cấu hình và giải quyết đường dẫn nhất quán theo thư mục dự án hoặc thư mục output đã cấu hình. |
| `schemas.py` | Định nghĩa cấu trúc dữ liệu chung cho văn bản, chunk, kết quả tìm kiếm và câu trả lời; bổ sung khi cần. |
| `storage.py` | Hàm đọc/ghi JSON, JSONL và manifest dùng lại giữa các bước. |
| Các file `__init__.py` | Đánh dấu package Python; ban đầu để trống. |

### Tải và xử lý dữ liệu: `src/legal_rag/data/`

| File | Đầu vào và công việc | Đầu ra |
|---|---|---|
| `download.py` | Dataset và revision từ cấu hình; tải file nguồn hiện hành, tận dụng cache đúng revision nếu có. | Các file nguồn và `data/raw/manifest.json`. |
| `sample.py` | File metadata và content; kiểm tra ID, ghép theo `id`, chọn 200 văn bản hợp lệ. Khi có danh sách ID đã chốt, dùng lại danh sách đó. | `sample_200_ids.json`, `documents.jsonl` và thông tin kiểm tra mẫu. |
| `clean.py` | Văn bản mẫu còn nội dung HTML; chuyển thành text, chuẩn hóa Unicode và khoảng trắng, giữ cấu trúc cần thiết. | `cleaned_documents.jsonl`. |
| `chunk.py` | Văn bản đã làm sạch; chia chunk ưu tiên ranh giới pháp lý, tạo ID ổn định và gắn metadata nguồn. | `chunks.jsonl` và thông tin cấu hình/số lượng chunk. |

Chỉ ghi vị trí Điều/Khoản/Điểm khi trích xuất đủ tin cậy. Không suy đoán vị trí bị thiếu. Dữ liệu `relationships` được tải và lưu nhưng chưa tham gia retrieval của MVP.

### Kết nối model: `src/legal_rag/models/`

| File | Trách nhiệm |
|---|---|
| `embedding.py` | Cung cấp hàm tạo document embedding và query embedding; quản lý batch, cách định dạng đầu vào và kết nối hoặc nạp model theo cách đã chốt. |
| `llm.py` | Gửi prompt tới dịch vụ LLM, nhận phản hồi và xử lý lỗi kết nối. |

Tạo corpus embedding và query embedding phải dùng cùng model/revision, kích thước vector và cách định dạng/chuẩn hóa tương thích. Đổi từ GPU sang CPU hoặc đổi thư viện chạy model không tự đảm bảo tính tương thích; cần kiểm tra ở giai đoạn triển khai.

### Lập chỉ mục và tìm kiếm: `src/legal_rag/retrieval/`

| File | Trách nhiệm |
|---|---|
| `bm25.py` | Tokenize text, xây/lưu BM25, nạp index và tìm top-k chunk. Dùng cùng hàm tokenization cho indexing và query; lưu đủ ánh xạ để lấy ID, text và metadata. |
| `dense.py` | Gọi module embedding, ghi chunk/vector/metadata vào Chroma và truy vấn bằng query embedding. |
| `hybrid.py` | Chọn phương pháp BM25/dense/hybrid; với hybrid, gọi hai retriever rồi gộp bằng RRF và loại trùng theo `chunk_id`. |

Xây và tìm kiếm của cùng một loại index nằm trong cùng module. Không tạo thêm thư mục `indexing/` với các file gần giống. BM25 và dense phải lập chỉ mục đúng cùng phiên bản `chunks.jsonl`.

### Sinh câu trả lời: `src/legal_rag/generation/`

| File | Trách nhiệm |
|---|---|
| `answer.py` | Nhận câu hỏi, gọi retrieval, dựng context, gọi LLM và trả câu trả lời kèm nguồn. Kiểm tra tham chiếu nguồn theo các chunk thực sự được truy xuất. |
| `prompt.txt` | Hướng dẫn LLM bám vào chứng cứ, tham chiếu nguồn và thông báo khi thiếu thông tin. |

Định danh, tên văn bản và URL trích dẫn được lấy từ metadata đã lưu. CLI và API dùng chung luồng trả lời này. UI gửi yêu cầu đến API.

### Đánh giá: `src/legal_rag/evaluation/`

| File | Trách nhiệm |
|---|---|
| `dataset.py` | Đọc câu hỏi, kiểm tra ID câu hỏi và nhãn chứng cứ có tồn tại trong corpus; đọc phần chia dùng để điều chỉnh hoặc báo cáo cuối. |
| `metrics.py` | Tính Recall@k, MRR@k và tổng hợp độ trễ từ kết quả đã đo. |
| `runner.py` | Chạy các phương pháp trên bộ câu hỏi, đo thời gian và lưu kết quả từng lần chạy. |

Câu ngoài phạm vi corpus được đánh dấu riêng; không đưa vào cách tính Recall/MRR như câu có chứng cứ. Đánh giá khả năng từ chối và chất lượng câu trả lời riêng. LLM có thể hỗ trợ gợi ý câu hỏi nhưng nhãn chứng cứ cần được kiểm tra thủ công.

### Demo: `src/legal_rag/app/`

| File | Trách nhiệm |
|---|---|
| `api.py` | API nhận câu hỏi, gọi luồng trả lời và trả câu trả lời, nguồn cùng thông tin retrieval cần thiết. |
| `ui.py` | Giao diện hỏi đáp đơn giản, gửi yêu cầu đến API và hiển thị câu trả lời/nguồn. |

Làm API và UI sau khi pipeline terminal chạy ổn. Framework và hình thức triển khai được chốt ở giai đoạn demo.

## 5. Code, dữ liệu và kết quả khác nhau thế nào?

`src/legal_rag/data/` chứa code xử lý dữ liệu. `data/` ở thư mục gốc chứa dữ liệu thật và index được tạo khi chạy code. Tương tự, `src/legal_rag/evaluation/` chứa code đánh giá, còn `eval/` chứa câu hỏi và nhãn dùng để đánh giá.

| Vị trí | Nội dung và cách tạo |
|---|---|
| `data/raw/metadata/`, `content/`, `relationships/` | Toàn bộ file nguồn của ba phần hiện hành; giữ nguyên nội dung, có thể gồm nhiều file Parquet tùy nguồn. |
| `data/raw/manifest.json` | Dataset, revision, danh sách file và kích thước để truy nguồn bản tải. |
| `documents.jsonl` | Mỗi dòng là một văn bản trong 200 văn bản đã ghép metadata, còn nội dung gốc. |
| `cleaned_documents.jsonl` | Mỗi dòng là một văn bản sau làm sạch, giữ định danh và metadata nguồn. |
| `chunks.jsonl` | Mỗi dòng là một chunk gồm `chunk_id`, text, `doc_id`, thứ tự và metadata nguồn; đầu vào chung cho BM25 và dense. |
| Manifest của dữ liệu xử lý | Nguồn, danh sách mẫu hoặc dấu nhận diện mẫu, cấu hình xử lý và số lượng kết quả ở các bước. |
| `bm25.pkl` | BM25 đã lưu cùng dữ liệu/ánh xạ cần để trả về đúng chunk. Chỉ nạp artifact tin cậy do dự án tạo. |
| `chroma/` | Thư mục database Chroma; chứa text, metadata, vector và dữ liệu nội bộ phục vụ truy vấn. Không tự sửa file nội bộ. |
| Manifest của index | Dấu nhận diện corpus/chunks, cấu hình BM25, cấu hình embedding và phiên bản Chroma để phát hiện index không khớp dữ liệu. |
| `eval/sample_200/questions.jsonl` | Bộ 30–50 câu hỏi có nhãn được kiểm tra, chứng cứ đúng, loại câu và phần chia đánh giá. |
| `results/<run_id>/config.json` | Cấu hình thực tế và định danh corpus/index của lần đánh giá. |
| `results/<run_id>/retrieval.jsonl` | Kết quả theo từng câu hỏi và từng phương pháp: chunk ID, thứ hạng và thời gian. |
| `results/<run_id>/metrics.json` | Các chỉ số tổng hợp của lần chạy. |
| `results/<run_id>/answer_review.jsonl` | Câu trả lời và nhận xét/nhãn đánh giá thủ công khi đến giai đoạn generation; không mặc định lấy LLM làm người xác nhận đúng. |

File JSONL chứa một JSON object trên mỗi dòng. Các manifest là thông tin mô tả artifact, không thay thế nội dung văn bản hoặc vector.

## 6. Luồng chạy và nguyên tắc một CLI

### Ingestion

```text
configs/project.yaml
  -> download.py
  -> data/raw/ (toàn bộ nguồn đã khóa revision)
  -> sample.py + danh sách ID cố định
  -> documents.jsonl (200 văn bản)
  -> clean.py
  -> cleaned_documents.jsonl
  -> chunk.py
  -> chunks.jsonl
       -> bm25.py -> bm25.pkl
       -> dense.py + models/embedding.py -> chroma/
```

### Query và trả lời

```text
Câu hỏi từ CLI hoặc API
  -> retrieval/hybrid.py chọn BM25, dense hoặc hybrid
       -> BM25 tìm trên index từ khóa
       -> dense tạo query embedding rồi tìm trong Chroma
       -> hybrid gộp hai danh sách bằng RRF
  -> các chunk và metadata nguồn
  -> generation/answer.py dựng context
  -> models/llm.py + prompt.txt
  -> câu trả lời và nguồn có thể đối chiếu
```

### Đánh giá

```text
questions.jsonl + corpus/index tương ứng
  -> evaluation/dataset.py kiểm tra nhãn
  -> evaluation/runner.py chạy retrieval và đo thời gian
  -> evaluation/metrics.py tính chỉ số
  -> results/<run_id>/
  -> đánh giá câu trả lời riêng khi đã có generation
```

Một đầu vào terminal dự kiến:

```bash
python -m legal_rag.cli <command> --config configs/project.yaml
```

Các subcommand được bổ sung dần: `download-data`, `select-sample`, `clean-data`, `prepare-chunks`, `build-bm25`, `build-chroma`, `search`, `ask`, `evaluate`.

CLI chỉ phân tích lệnh và gọi module. Ví dụ `build-bm25` gọi hàm xây index trong `retrieval/bm25.py`, còn `search --method bm25` dùng hàm tìm kiếm của cùng module. Không tạo thêm bộ `scripts/*.py` chứa lại logic đó. CLI chỉ hiển thị kết quả; module xử lý trả dữ liệu có cấu trúc để API và evaluation dùng lại.

## 7. Local, Kaggle và lưu vào Git

- Dùng cùng code Python, điều chỉnh đường dẫn output và URL dịch vụ qua cấu hình.
- Hướng đã chốt ngày 2026-10-16: `models/embedding.py` gọi API vLLM cho cả document và query; `retrieval/dense.py` xây và tìm kiếm Chroma, không tự load model. Cùng module chạy được ở local hoặc Kaggle; notebook nếu dùng chỉ khởi động dịch vụ và gọi lệnh, không chứa logic tạo index riêng.
- Có thể xây Chroma trên Kaggle rồi tải về local; query local gọi vLLM trên Kaggle để lấy vector và tìm trong Chroma local. Cần xác minh kết nối tới endpoint, phiên Kaggle hoạt động và cấu hình embedding tương thích; chưa chốt model/vLLM hoặc cách mở endpoint.
- Trên Kaggle, chạy các file/module bằng lệnh terminal trong môi trường phù hợp; notebook không phải nơi chứa logic của project.
- Khi chuyển index về local, sao chép đủ `data/indexes/sample_200/` gồm BM25, toàn bộ thư mục Chroma và manifest sau khi tiến trình ghi đã kết thúc.
- Lưu phiên bản Chroma tương thích và giữ nguyên cấu hình embedding. Ở local vẫn tạo embedding cho câu hỏi mới; không tính lại document embedding chỉ vì đổi máy.
- Giữ `chunks.jsonl` và metadata nguồn để kiểm tra, xây lại index và đối chiếu nhãn nếu cần.
- Đưa code, `pyproject.toml`, cấu hình không chứa bí mật, tài liệu, 200 ID cố định và bộ câu hỏi vào Git. Bổ sung file khóa phiên bản khi đến giai đoạn tái lập môi trường.
- Bỏ dữ liệu nguồn, dữ liệu xử lý, index lớn, môi trường Python và cache khỏi Git. Chỉ chọn kết quả benchmark cần công bố để đưa vào Git, không tự động lưu mọi lần chạy.

## 8. Thứ tự triển khai từng file

1. Tạo tài liệu `PROJECT_STRUCTURE.md` này trước.
2. Bắt đầu bằng một file `pyproject.toml`, rồi tạo từng file cấu hình cần thiết. Dùng môi trường Conda `legal-rag` hiện có; kiểm tra cài/import package khi đủ các file tối thiểu.
3. Viết tải dữ liệu, rồi bổ sung lệnh `download-data` vào CLI.
4. Kiểm tra schema và chất lượng dữ liệu thực tế; viết chọn mẫu, clean và chunk theo thứ tự. Bổ sung schema/hàm lưu khi có nhu cầu cụ thể.
5. Viết BM25 và kiểm tra top-k kết quả trước khi thêm LLM.
6. Chốt embedding model/cách chạy, viết embedding và Chroma; kiểm tra query và khả năng chuyển index từ Kaggle về local.
7. Tạo bộ câu hỏi có nhãn, đo hai baseline, thêm hybrid rồi so sánh trên cùng bộ đánh giá.
8. Viết generation và kiểm tra câu trả lời/trích dẫn/hành vi thiếu chứng cứ.
9. Làm API, UI và hoàn thiện README cùng benchmark portfolio.

Mỗi lượt chỉ tạo hoặc sửa file cần thiết cho bước đang làm. Một bước có thể cần nhiều lượt vì các file phụ thuộc nhau; không yêu cầu file đầu tiên phải chạy độc lập khi package chưa đủ. Không tạo toàn bộ khung code rỗng trong một lượt.

## 9. Kiểm tra phù hợp với từng giai đoạn

| Vị trí | Các hành vi cần kiểm tra |
|---|---|
| `tests/fixtures/` | Một số mẫu dữ liệu nhỏ, có thể kiểm soát được, không chứa toàn bộ dataset. |
| `test_data_pipeline.py` | Ghép đúng ID; xử lý thiếu/trùng ID; clean giữ nội dung cần thiết; chunk có ID ổn định và truy về văn bản; metadata không bị mất. |
| `test_retrieval.py` | Hai index dùng đúng corpus; ánh xạ kết quả đúng chunk; RRF gộp thứ hạng và loại trùng; phát hiện cấu hình index/corpus không khớp. |
| `test_evaluation.py` | Nhãn chứng cứ hợp lệ; Recall/MRR đúng trên ví dụ tính tay; câu ngoài phạm vi được xử lý riêng. |

Các file test được tạo dần khi có hành vi cần xác minh. Ngoài test nhỏ, kiểm tra tích hợp thực tế khi tải dữ liệu, chạy Chroma và chuyển index giữa môi trường. Các giá trị chunk size, overlap, model, thông số retrieval và framework demo chỉ được chốt sau khi đến giai đoạn tương ứng; tài liệu này xác định nơi đặt chức năng, không giả định các quyết định đó đã xong.
