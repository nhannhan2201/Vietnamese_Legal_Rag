# Kế hoạch project: Vietnamese Legal RAG

## Mục tiêu

Xây dựng project portfolio cho vị trí AI Engineer Intern: hệ thống hỏi đáp trên dữ liệu văn bản pháp luật Việt Nam, trả lời dựa trên đoạn nguồn có thể kiểm tra, và có benchmark so sánh các phương pháp retrieval. Bản chạy đầu dùng 200 văn bản để kiểm chứng toàn bộ pipeline; thiết kế phải cho phép tăng quy mô mà không viết lại kiến trúc.

Đây là kế hoạch hiện tại, chưa phải đặc tả cố định. Các quyết định về embedding model, LLM và giao diện sẽ được chốt sau khi kiểm tra dữ liệu và điều kiện chạy thực tế.

## Phạm vi MVP đã chốt

- Dùng bản dữ liệu hiện hành của `th1nhng0/vietnamese-legal-documents` làm nguồn; tải đầy đủ các file `metadata`, `content` và `relationships`, nhưng ban đầu chỉ xử lý và lập chỉ mục 200 văn bản hợp lệ. Không cần tải các config `legacy` cho bản đầu.
- Khóa revision/commit của dataset, lưu danh sách 200 `doc_id` cố định và ghi rõ corpus thử nghiệm chỉ bao phủ 200 văn bản.
- Xây hai baseline retrieval trên **cùng tập chunk**: BM25 và dense search.
- Thử hybrid retrieval bằng Reciprocal Rank Fusion (RRF), so sánh với hai baseline.
- Sinh câu trả lời từ các chunk truy xuất được, kèm nguồn và đoạn trích có thể đối chiếu.
- Đánh giá retrieval và chất lượng câu trả lời riêng biệt.
- **Chưa làm graph retrieval, agent, hoặc tự tách query thành metadata filter.** Chỉ bổ sung khi phân tích lỗi và benchmark cho thấy nhu cầu cụ thể.

## Môi trường phát triển đã chốt

- Dùng môi trường Conda `legal-rag` với Python 3.11 ở local; môi trường này đã được tạo.
- Conda quản lý Python và môi trường. Ở giai đoạn đầu, khai báo package và dependency Python trong `pyproject.toml`, rồi cài bằng pip bên trong môi trường Conda.
- Chưa thêm file khai báo môi trường hoặc danh sách dependency riêng. Cách khóa phiên bản để chạy lại trên Kaggle và máy khác sẽ được bổ sung sau khi pipeline đầu tiên chạy được.
- `.env.example` chỉ mô tả tên biến môi trường cho token/API key, không chứa bí mật thật và không phải cấu hình môi trường Conda.
- Tiếp tục triển khai từng file theo `PROJECT_STRUCTURE.md`; file tiếp theo là `pyproject.toml`.

## Luồng dữ liệu dự kiến

```text
Nguồn văn bản
  -> tải đầy đủ các file nguồn của bản hiện hành
  -> ghép content với metadata theo id; chọn 200 văn bản có nội dung
  -> lưu danh sách 200 id và dữ liệu mẫu cố định
  -> làm sạch, chuẩn hóa
  -> chia chunk
  -> (1) BM25 index trên text của chunk
     (2) embedding + vector index trên cùng các chunk

Câu hỏi
  -> BM25 / dense / hybrid retrieval
  -> chọn các chunk liên quan
  -> LLM trả lời dựa trên nội dung chunk
  -> hiển thị trích dẫn từ metadata của chunk
```

## Các giai đoạn thực hiện

### 1. Khóa nguồn dữ liệu và chọn 200 văn bản thử nghiệm

- Ghi repo Hugging Face, revision/commit, ngày tải, schema và kích thước các file của bản hiện hành.
- Tải toàn bộ file `metadata.parquet`, `content.parquet` và `relationships.parquet` của revision đã chọn. "Tải dữ liệu nguồn" khác với "đưa dữ liệu vào index": chỉ 200 văn bản thử nghiệm được làm sạch, chia chunk và embedding ở lượt đầu.
- Chọn 200 ID khác nhau có cả metadata và `content_html` không rỗng; không lấy độc lập 200 dòng đầu của từng bảng. Kiểm tra tính đa dạng về loại văn bản, lĩnh vực, độ dài và trạng thái.
- Lưu manifest gồm revision, quy tắc chọn mẫu, seed nếu có, và danh sách 200 ID để chạy lại đúng corpus.

**Hoàn thành khi:** có 200 văn bản hợp lệ cố định và báo cáo kiểm tra dữ liệu. Demo phải nói rõ chỉ trả lời dựa trên 200 văn bản đã index, dù file nguồn chứa toàn bộ dataset.

### 2. Tải và kiểm tra dữ liệu thô

- Viết script `.py` trong repo để đọc file nguồn đã tải, ghép `content.id` với `metadata.id`, và xuất dữ liệu của đúng 200 ID thành file trung gian.
- Giữ bản thô và metadata của 200 văn bản để có thể kiểm tra hoặc chạy lại mà không cần đọc lại toàn bộ dữ liệu nguồn mỗi lần.
- Kiểm tra ID trùng, nội dung rỗng, metadata thiếu và lỗi mã hóa ký tự.

**Hoàn thành khi:** có tập văn bản thô với nguồn gốc truy ngược được và báo cáo kiểm tra dữ liệu cơ bản.

### 3. Làm sạch và chia chunk

- Loại HTML/phần trình bày thừa; chuẩn hóa Unicode và khoảng trắng.
- Ưu tiên giữ ranh giới Điều, Khoản, Điểm khi chia; kiểm tra thủ công mẫu chunk trước khi chốt kích thước và overlap.
- Mỗi chunk có `chunk_id` ổn định, nội dung, `doc_id`, `chunk_index` và metadata nguồn. Chỉ ghi số Điều/Khoản/Điểm nếu trích xuất đủ tin cậy.

**Hoàn thành khi:** chunk có thể truy về văn bản gốc, không bị trùng ID, và các ví dụ được kiểm tra không mất phần ngữ cảnh quan trọng.

### 4. Xây BM25 và dense index

- **Quyết định ngày 2026-10-16:** dùng một bộ module Python để xây dense index ở local hoặc Kaggle. Module embedding gọi API của model được serve bằng vLLM; không tự load model trong tiến trình xây index và không viết logic tạo index riêng trong notebook.
- `models/embedding.py` dùng chung để gọi API cho document và query; `retrieval/dense.py` đọc chunk, gọi embedding theo batch, lưu và truy vấn Chroma. URL endpoint và đường dẫn được cấu hình theo môi trường; Chroma nằm trên máy chạy module xây index.
- Luồng dự kiến: chạy module xây Chroma trên Kaggle, đóng tiến trình ghi rồi tải toàn bộ thư mục Chroma cùng manifest về local. Khi query local, gọi endpoint vLLM trên Kaggle để lấy query vector rồi tìm trong Chroma local. Phương án này phụ thuộc endpoint truy cập được và phiên Kaggle còn hoạt động; đường kết nối chưa được xác minh.
- Model/revision, phiên bản vLLM và Chroma, định dạng document/query, kích thước vector và chuẩn hóa phải được chốt và kiểm tra tương thích trước khi xây dense index. Hiện chưa chốt model hoặc triển khai endpoint.
- BM25 lập chỉ mục từ nội dung của từng chunk; bắt đầu với baseline đơn giản rồi đo lỗi do tokenization tiếng Việt.
- Dense tạo embedding cho cùng tập chunk và lưu vector, text, metadata trong Chroma. Bản thử dùng Chroma `PersistentClient` lưu vào một thư mục, không cần Docker Compose.
- Viết các script chạy bằng lệnh terminal, dùng đường dẫn và URL model qua cấu hình để có thể clone repo và chạy trên máy local có GPU hoặc Kaggle. Trên Kaggle, output cần được lưu để tải về; có thể chuyển toàn bộ thư mục Chroma sang local với phiên bản Chroma tương thích, không nạp lại các chunk/vector.
- Khi query ở local, vẫn phải tạo embedding cho câu hỏi bằng cùng model và cùng cách tiền xử lý như lúc index; BM25 được lưu/xây riêng.
- Tạo lệnh/script hỏi thử để in top-k kết quả của từng phương pháp trước khi dùng LLM.

**Hoàn thành khi:** cùng một query trả ra được hai danh sách kết quả có ID, nội dung và nguồn.

### 5. Tạo bộ đánh giá retrieval

- Cho bản 200 văn bản, chuẩn bị khoảng 30–50 câu hỏi có nhãn kiểm tra thủ công. Đọc Điều/đoạn trong corpus, viết câu hỏi tự nhiên từ nội dung đó, ghi `chunk_id` hoặc ID Điều chứa chứng cứ và rà soát các đoạn khác cũng có thể trả lời. LLM chỉ được hỗ trợ gợi ý cách diễn đạt, không tự xác nhận nhãn đúng.
- Gồm câu khớp từ khóa/số hiệu, câu diễn đạt tự nhiên, câu cần nhiều đoạn; đánh dấu riêng câu không có đáp án trong corpus để kiểm tra khả năng từ chối trả lời.
- Tách phần dùng để điều chỉnh và phần báo kết quả cuối. Dùng Recall@5 và MRR@5 cho các câu có chứng cứ; ghi độ trễ retrieval. Đánh giá câu ngoài phạm vi bằng chỉ số từ chối trả lời riêng.

**Hoàn thành khi:** có thể chạy lại benchmark trên cùng corpus và cùng bộ câu hỏi.

### 6. So sánh và cải thiện retrieval

- Đo BM25 và dense riêng; đọc các trường hợp thất bại.
- Gộp danh sách bằng RRF; bỏ trùng theo `chunk_id`; đo lại cùng bộ câu hỏi.
- Chỉ thêm reranker nếu kết quả đo cho thấy nó giải quyết một lỗi đáng kể so với chi phí/độ trễ tăng thêm.

**Hoàn thành khi:** có bảng so sánh BM25, dense, hybrid và phân tích ít nhất vài trường hợp cải thiện hoặc suy giảm.

### 7. Sinh câu trả lời và trích dẫn

- Đưa câu hỏi và các chunk được chọn vào LLM; yêu cầu câu trả lời bám vào chứng cứ.
- Khi thiếu chứng cứ, trả lời rõ rằng chưa đủ thông tin trong tập dữ liệu.
- Trả về nội dung trả lời và danh sách nguồn: văn bản, vị trí nếu có, đoạn trích, URL.
- Trích dẫn được dựng từ metadata đã lưu, không để LLM tự đoán định danh hay URL nguồn.

**Hoàn thành khi:** người xem có thể đối chiếu từng câu trả lời với các đoạn đã truy xuất.

### 8. Đánh giá câu trả lời

- Kiểm tra riêng độ đúng của câu trả lời, việc trích dẫn có hỗ trợ kết luận, và hành vi khi không có đáp án.
- Phân loại lỗi theo tầng: dữ liệu, chunking, retrieval hoặc generation.
- Không xem câu trả lời trôi chảy là bằng chứng đúng.

**Hoàn thành khi:** có báo cáo kết quả và các giới hạn thực tế của hệ thống.

### 9. Demo và đóng gói portfolio

- Cung cấp API và giao diện hỏi đáp đơn giản.
- Viết README: mục tiêu, phạm vi, nguồn dữ liệu, sơ đồ, cách chạy ingestion/query/evaluation, benchmark, ví dụ thành công và thất bại.
- Chuẩn bị đường chạy nhanh trên một tập nhỏ để người khác có thể thử lại.

**Hoàn thành khi:** repo có thể tái lập và người phỏng vấn hiểu được các lựa chọn kỹ thuật, số liệu và đóng góp của người làm.

## Vai trò metadata trong MVP

Metadata **không phải** embedding hay vector database. Mỗi chunk có nội dung và metadata đi kèm. Trong MVP, metadata dùng để:

1. Ghép nội dung với văn bản gốc trong ingestion.
2. Tạo ID ổn định, bỏ trùng và truy ngược chunk.
3. Đối chiếu kết quả retrieval với nhãn đánh giá.
4. Hiển thị nguồn và trích dẫn khi trả lời.

MVP **không tự trích xuất số hiệu/Điều/Khoản/ngày từ câu hỏi để lọc metadata ở bước search**. Đó là một cải tiến có thể xem xét sau khi phân tích lỗi. Không khẳng định hiệu lực của một điều khoản chỉ dựa trên trường trạng thái của cả văn bản.

## Repo tham khảo và lưu ý

- Repo: https://github.com/ThuanNaN/aio-agentic-rag
- Học luồng `load -> clean -> chunk -> Chroma/BM25`, BM25 và dense trên cùng tập chunk, hybrid bằng RRF, và cách benchmark.
- Không mặc định sao chép kiến trúc graph/agent hay số benchmark của repo. Bộ đánh giá của project này phải được tạo và đo lại trên corpus của chính mình.
- Script `build_eval_set.py` trong repo tham khảo chỉ xuất 8 câu hỏi mẫu với `expected_doc_ids` rỗng; nhãn đúng vẫn cần được điền và kiểm tra. Không lấy bảng số liệu minh họa của repo/PDF làm kết quả project này.
- BM25 trong repo tham khảo tokenizes bằng `lower().split()`; đây là baseline cần kiểm chứng với tiếng Việt.

## Quyết định còn mở

- Quy tắc lấy mẫu 200 văn bản đại diện và quy mô giai đoạn mở rộng sau bản thử.
- Cách trích xuất vị trí Điều/Khoản/Điểm từ định dạng dữ liệu thực tế.
- Embedding model, LLM và cách chạy/serve model thực tế; môi trường phát triển local đã chốt là Conda `legal-rag` với Python 3.11. Code cần chạy được bằng các script `.py` ở local hoặc trên Kaggle.
- Giao diện demo và cách triển khai.

### Chốt bộ câu hỏi ngày 2026-10-17

- Người dùng đã duyệt 30 câu tại `eval/sample_200/questions.jsonl`; `review_status=verified`.
- Mỗi câu giữ question_id, question, reference_answer, evidence, review_status, split. Nhãn gốc là doc_id + quote + vị trí trong văn bản sạch; không phụ thuộc chunk ID.
- Có 15 câu nêu số hiệu và 15 câu không nêu số hiệu; 31 đoạn bằng chứng (q028 có hai đoạn thay thế).
- Chưa chia dev/test hoặc chạy benchmark. Bước tiếp theo là chốt cách đánh giá, chia dev/test trước khi điều chỉnh retrieval, và ánh xạ bằng chứng sang chunk của corpus hiện tại.

### Điều chỉnh đánh giá và dữ liệu ngày 2026-10-17

- Bộ 30 câu hiện gồm 24 câu một văn bản (giữ phê duyệt) và 6 câu hai văn bản chờ duyệt lại: q008, q014, q021, q023, q026, q028. Quyết định này thay mô tả trước về bộ 30 câu một nguồn đã chốt.
- Giữ evidence theo vị trí văn bản sạch; nhiều khoảng trong cùng doc_id được phép. Chunk đúng phải bao trọn ít nhất một khoảng có cùng doc_id.
- Recall@5 theo doc_id khác nhau của top 5 chunk; Hit@5/MRR@5 theo chunk chứa bằng chứng. Không dùng chunk Recall trong bản đầu. Đo thêm thời gian retrieval trung bình.
- Hit/MRR không thể hiện đủ cả hai nguồn; chưa chia dev/test, chưa chạy benchmark.

### Chốt phiên bản có câu hai nguồn ngày 2026-10-17

- Người dùng đã chốt toàn bộ 30 câu hiện tại, gồm 24 câu một văn bản và 6 câu hai văn bản (q008, q014, q021, q023, q026, q028); tất cả review_status=verified. Xác nhận này thay trạng thái chờ duyệt sáu câu ở mục trước.
- Tổng 36 khoảng bằng chứng, 15 câu có số hiệu và 15 câu không có. Giữ nguyên câu hỏi, đáp án, doc_id, quote và vị trí nguồn; chỉ cập nhật trạng thái duyệt và checksum.
- Bước tiếp theo là viết code đánh giá theo giao thức trong eval/sample_200/manifest.json; chưa chia dev/test hoặc chạy benchmark.

### Sửa nhãn thay thế q028 sau lần đánh giá đầu

- Bổ sung Điều 3 của doc_id 141383 vào evidence q028 theo yêu cầu người dùng; giữ Điều 10 và bằng chứng doc_id 162690. q028 có 2 văn bản, 3 khoảng; tổng bộ dữ liệu có 37 khoảng.
- Không đổi câu hỏi, đáp án hoặc quy tắc metrics. Kết quả lần chạy 20261017_083537_121464_c44f502d dựa nhãn cũ cần được chấm lại hoặc chạy lại, không ghi đè kết quả gốc.

### Luồng trả lời RAG có nguồn

- `generation/answer.py` chứa `SYSTEM_PROMPT` trong cùng file; không tạo `prompt.txt`. Hàm `answer_question` nhận index và client đã tạo để tái sử dụng.
- Hybrid RRF mặc định theo lựa chọn người dùng; vẫn chọn được BM25 hoặc dense. Đánh số nguồn theo chunk, không gộp theo doc_id.
- Output gồm câu trả lời, trạng thái, danh sách số nguồn được trích dẫn và nguyên văn các nguồn thực sự gửi cho LLM. UI bấm trích dẫn làm sau; chưa tạo URL ngoài.
- Kiểm tra trích dẫn chỉ xác nhận định dạng và số nguồn hợp lệ, không tự xác nhận từng nhận định đúng. Không có kết quả thì không gọi LLM; thiếu căn cứ hoàn toàn thì dùng câu từ chối cố định.
- Đã kiểm tra bằng retrieval/LLM giả; lần triển khai này chưa gọi API thật hoặc chạy bộ đánh giá generation.

### API phục vụ luồng RAG

- `app/api.py` dùng FastAPI, cung cấp `POST /ask` (`question`, `method` mặc định hybrid) và `GET /health`; dùng nguyên `answer_question()` hiện có với top 5 mặc định.
- Nạp index và tạo EmbeddingClient/LLMClient trong lifespan một lần mỗi tiến trình, đóng các HTTP client khi dừng. Không load tài nguyên hoặc gọi API khi chỉ import module.
- Local demo: `python -m uvicorn legal_rag.app.api:app --host 127.0.0.1 --port 8001`, một worker; tài liệu tương tác ở `/docs`. Health không kiểm tra kết nối thực tế đến nhà cung cấp.
- Lỗi request trả 422, lỗi pipeline dự kiến trả 502, lỗi nội bộ khác trả 500; không trả thông tin key hoặc phản hồi provider ra client. Không tự retry và không dựng lại index.

### Giao diện web Luật Việt

- UI HTML/CSS/JavaScript trong `src/legal_rag/app/static/`, FastAPI phục vụ trang `/` và asset `/static/`; không cần build frontend hoặc thêm dependency.
- Tông navy, kem, vàng đồng; ảnh cán cân công lý/sách luật tạo bằng imagegen; bố cục responsive cho máy tính và điện thoại.
- Gửi câu hỏi đến `/ask`, hybrid mặc định; có lựa chọn BM25/dense. Lịch sử lưu trong bộ nhớ tab, không dùng làm hội thoại đầu vào cho model.
- Bấm trích dẫn mở nguyên văn chunk cùng metadata trong bảng nguồn. Hiển thị thiếu bằng chứng/lỗi rõ ràng, không tự gửi lại hoặc gọi model từ trình duyệt.
- `.env` chỉ dùng ở backend. UI hiển thị Markdown cơ bản bằng DOM an toàn, không render HTML từ model hoặc nguồn.
- Chạy cùng lệnh Uvicorn ở cổng 8001 rồi mở `/`. Cần giữ endpoint embedding và dịch vụ LLM hoạt động khi hỏi thật.
