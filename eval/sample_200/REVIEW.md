# Bộ 30 câu hỏi — phiên bản có câu kết hợp hai văn bản

**Trạng thái:** người dùng đã chốt toàn bộ phiên bản hiện tại gồm 30 câu ngày 2026-10-17; tất cả review_status=verified.

## Cấu trúc và nguyên tắc

- Mỗi câu chỉ giữ question_id, question, reference_answer, evidence, review_status, split.
- Mỗi evidence gồm doc_id, quote, start_char, end_char; vị trí theo ký tự Python của văn bản sạch, cuối khoảng không bao gồm.
- Nhãn gốc không có chunk_id. Không gộp các đoạn ở xa thành khoảng dài; cho phép nhiều khoảng cùng văn bản nếu có bằng chứng trả lời thay thế.
- Câu hai văn bản yêu cầu hai ý từ hai nguồn: cần cả hai để trả lời đầy đủ. Hit/MRR chỉ kiểm tra tìm thấy ít nhất một khoảng, không biểu thị đủ toàn bộ đáp án.
- Câu so sánh phiên bản lịch sử phải trả lời theo phiên bản được hỏi, không suy ra các quy định đó cùng áp dụng hiện tại.
- Có 15 câu có số hiệu, 15 câu không có; 24 câu một văn bản và 6 câu hai văn bản. Chưa chia dev/test.

## Cách đánh giá đã chốt

- Recall@5 theo văn bản: số doc_id ground truth khác nhau xuất hiện trong top 5 chunk chia tổng số doc_id ground truth. Không đếm trùng; không lấy thêm chunk ngoài top 5 để bù trùng.
- Chunk đúng cho Hit/MRR: cùng doc_id và chứa toàn bộ ít nhất một khoảng evidence.
- Hit@5: 1 nếu có ít nhất một chunk đúng trong top 5, ngược lại 0.
- Điểm reciprocal rank của từng câu: 1/hạng chunk đúng đầu tiên trong top 5, không có thì 0. MRR@5 là trung bình trên các câu.
- Đo thời gian retrieval trung bình; dense/hybrid gồm gọi API và mạng, không gồm nạp index, chấm điểm và ghi kết quả.

## Giới hạn

- Chưa bảo đảm liệt kê hết mọi khoảng bằng chứng tương đương. Chưa có câu ngoài phạm vi.
- q009: metadata ghi Toàn quốc nhưng đầu văn bản xác định HĐND tỉnh Thanh Hóa; câu hỏi dựa nội dung nguồn.
- Người dùng đã chốt cả sáu câu hai nguồn. Đã chạy đánh giá ban đầu; cần chấm lại sau khi bổ sung bằng chứng thay thế cho q028. Chưa chia dev/test.

## q001

**Câu hỏi:** Theo Luật Tiếp cận thông tin, tiếp cận thông tin gồm những hoạt động nào?

**Đáp án tham chiếu:** Đọc, xem, nghe, ghi chép, sao chép và chụp thông tin.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 101873 — **Số hiệu:** 104/2016/QH13
**Tiêu đề:** Tiếp cận thông tin
**Vị trí trong text sạch:** [1005:1086]

```text
3. Tiếp cận thông tin là việc đọc, xem, nghe, ghi chép, sao chép, chụp thông tin.
```

**Xác minh:** verified.

## q002

**Câu hỏi:** Theo Quy định về thủ tục cấp giấy phép khai thác mỏ đá quý do Bộ Công nghiệp nặng ban hành năm 1994, tổ chức, cá nhân đã trúng thầu khai thác mỏ phải gửi bao nhiêu bộ hồ sơ và gửi đến đâu?

**Đáp án tham chiếu:** Gửi 03 bộ hồ sơ đến Cục Quản lý tài nguyên khoáng sản Nhà nước để trình Bộ trưởng Bộ Công nghiệp nặng cấp giấy phép khai thác mỏ.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 10399 — **Số hiệu:** 72/QĐ-QLTN
**Tiêu đề:** Ban hành bản Quy định về thủ tục cấp giấy phép khai thác mỏ đá quý
**Vị trí trong text sạch:** [1039:1255]

```text
Điều 1. Tổ chức, cá nhân Việt Nam và nước ngoài đã trúng thầu khai thác mỏ đá quý phải gửi đến Cục Quản lý tài nguyên khoáng sản Nhà nước 03 bộ hồ sơ để trình Bộ trưởng Bộ Công nghiệp nặng cấp giấy phép khai thác mỏ.
```

**Xác minh:** verified.

## q003

**Câu hỏi:** Theo Quy tắc bảo hiểm khách du lịch trong nước của BAOVIET trong tập văn bản, người được bảo hiểm tham gia đua ngựa phải nộp thêm khoản gì để được bảo hiểm hoạt động này?

**Đáp án tham chiếu:** Phải nộp thêm phụ phí bảo hiểm cho BAOVIET theo quy định tại Biểu phí và số tiền bảo hiểm.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 10592 — **Số hiệu:** 06/TC-BH
**Tiêu đề:** Về việc ban hành các Quy tắc bảo hiểm khách du lịch
**Vị trí trong text sạch:** [1897:2208]

```text
2. Trường hợp người được bảo hiểm khảo sát, thám hiểm, biểu diễn nguy hiểm, đua xe, đua ngựa, đua thuyền, thi đấu có tính chất chuyên nghiệp các môn: bóng đá, đấm bốc, leo núi, lướt ván... chỉ được bảo hiểm với điều kiện đã nộp thêm phụ phí bảo hiểm cho BAOVIET theo quy định tại "Biểu phí và số tiền bảo hiểm".
```

**Xác minh:** verified.

## q004

**Câu hỏi:** Theo nghị định thành lập Cục Đường bộ Việt Nam trực thuộc Bộ Giao thông vận tải năm 1993, Cục trưởng chịu trách nhiệm trước ai?

**Đáp án tham chiếu:** Bộ trưởng Bộ Giao thông vận tải.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 10784 — **Số hiệu:** 7-CP
**Tiêu đề:** Về việc thành lập Cục đường bộ Việt nam trực thuộc Bộ giao thông vận tải
**Vị trí trong text sạch:** [605:765]

```text
Cục trưởng Cục Đường bộ chịu trách nhiệm trước Bộ trưởng Bộ Giao thông vận tải thực hiện chức năng quản lý Nhà nước chuyên ngành đường bộ trong phạm vi cả nước.
```

**Xác minh:** verified.

## q005

**Câu hỏi:** Theo Nghị định 150/2016/NĐ-CP, Văn phòng Chính phủ có vị trí như thế nào trong Chính phủ?

**Đáp án tham chiếu:** Là cơ quan ngang bộ của Chính phủ và là bộ máy giúp việc của Chính phủ, Thủ tướng Chính phủ.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 115596 — **Số hiệu:** 150/2016/NĐ-CP
**Tiêu đề:** NGHỊ ĐỊNH
Quy định chức năng, nhiệm vụ, quyền hạn
và cơ cấu tổ chức của Văn phòng Chính phủ
**Vị trí trong text sạch:** [359:471]

```text
Văn phòng Chính phủ là cơ quan ngang bộ của Chính phủ, là bộ máy giúp việc của Chính phủ và Thủ tướng Chính phủ.
```

**Xác minh:** verified.

## q006

**Câu hỏi:** Theo định nghĩa tại Điều 1 Nghị định 22/HĐBT, khoản thu về sử dụng vốn ngân sách được tính trên những loại vốn nào?

**Đáp án tham chiếu:** Vốn cố định và vốn lưu động do ngân sách Nhà nước cấp, cùng vốn có nguồn gốc từ ngân sách Nhà nước.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 11579 — **Số hiệu:** 22/HĐBT
**Tiêu đề:** Quy định chế độ thu và sử dụng vốn ngân sách Nhà nước
**Vị trí trong text sạch:** [264:494]

```text
Điều 1. - Thu về sử dụng vốn đối với các tổ chức kinh tế là khoản thu tính trên vốn (bao gồm vốn cố định, vốn lưu động) do ngân sách Nhà nước cấp và vốn có nguồn gốc từ ngân sách Nhà nước (gọi chung là vốn ngân sách Nhà nước cấp).
```

**Xác minh:** verified.

## q007

**Câu hỏi:** Theo Thông tư 15/2016/TT-BKHĐT, khi bổ sung yêu cầu vào hồ sơ lựa chọn nhà đầu tư PPP, có được đặt điều kiện tạo lợi thế cho một số nhà đầu tư gây cạnh tranh không bình đẳng không?

**Đáp án tham chiếu:** Không. Không được áp dụng điều kiện hạn chế sự tham gia hoặc tạo lợi thế cho một hay một số nhà đầu tư gây cạnh tranh không bình đẳng; việc bổ sung phải bảo đảm cạnh tranh, công bằng, minh bạch, hiệu quả kinh tế và không trái pháp luật đấu thầu.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 116335 — **Số hiệu:** 15/2016/TT-BKHĐT
**Tiêu đề:** Hướng dẫn lập hồ sơ mời sơ tuyển, hồ sơ mời thầu
lựa chọn nhà đầu tư thực hiện dự án đầu tư theo hình thức đối tác công tư
**Vị trí trong text sạch:** [1838:2348]

```text
1. Căn cứ quy mô, tính chất, lĩnh vực của từng dự án cụ thể, người có thẩm quyền, bên mời thầu có thể bổ sung các yêu cầu phù hợp trên cơ sở bảo đảm nguyên tắc cạnh tranh, công bằng, minh bạch và hiệu quả kinh tế trong quá trình lập, thẩm định, phê duyệt hồ sơ mời sơ tuyển, hồ sơ mời thầu; đảm bảo không trái với quy định của pháp luật về đấu thầu; không được áp dụng các điều kiện nhằm hạn chế sự tham gia của nhà đầu tư hoặc nhằm tạo lợi thế cho một hoặc một số nhà đầu tư gây ra cạnh tranh không bình đẳng.
```

**Xác minh:** verified.

## q008

**Câu hỏi:** Theo Luật sửa đổi Luật Di sản văn hóa năm 2009 và Luật Di sản văn hóa năm 2024, hai văn bản định nghĩa di sản văn hóa phi vật thể như thế nào?

**Đáp án tham chiếu:** Văn bản sửa đổi năm 2009 định nghĩa đây là sản phẩm tinh thần gắn với cộng đồng hoặc cá nhân, vật thể và không gian văn hóa liên quan, có giá trị lịch sử, văn hóa, khoa học, thể hiện bản sắc cộng đồng, được tái tạo và lưu truyền qua các thế hệ bằng truyền miệng, truyền nghề, trình diễn và hình thức khác. Luật năm 2024 định nghĩa là tri thức, kỹ năng, tập quán, biểu đạt văn hóa cùng đồ vật, đồ tạo tác, không gian liên quan, được cộng đồng, nhóm người, cá nhân thực hành, trao truyền qua nhiều thế hệ, hình thành bản sắc văn hóa, không ngừng được trao truyền, bảo vệ, tái tạo, sáng tạo và có giá trị lịch sử, văn hóa, khoa học.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 11750 — **Số hiệu:** 32/2009/QH12
**Tiêu đề:** Sửa đổi, bổ sung một số điều của Luật Di sản văn hóa
**Vị trí trong text sạch:** [428:766]

```text
“1. Di sản văn hóa phi vật thể là sản phẩm tinh thần gắn với cộng đồng hoặc cá nhân, vật thể và không gian văn hóa liên quan, có giá trị lịch sử, văn hóa, khoa học, thể hiện bản sắc của cộng đồng, không ngừng được tái tạo và được lưu truyền từ thế hệ này sang thế hệ khác bằng truyền miệng, truyền nghề, trình diễn và các hình thức khác.”
```

### Bằng chứng 2

**doc_id:** 173024 — **Số hiệu:** 45/2024/QH15
**Tiêu đề:** Di sản văn hóa
**Vị trí trong text sạch:** [1042:1380]

```text
1. Di sản văn hóa phi vật thể là tri thức, kỹ năng, tập quán, biểu đạt văn hóa cùng đồ vật, đồ tạo tác, không gian liên quan được cộng đồng, nhóm người, cá nhân thực hành, trao truyền qua nhiều thế hệ và hình thành nên bản sắc văn hóa của họ, không ngừng được trao truyền, bảo vệ, tái tạo, sáng tạo, có giá trị lịch sử, văn hóa, khoa học.
```

**Xác minh:** verified.

## q009

**Câu hỏi:** Theo kế hoạch đầu tư công năm 2017 của tỉnh Thanh Hóa, tổng nguồn vốn đầu tư công do tỉnh quản lý là bao nhiêu triệu đồng?

**Đáp án tham chiếu:** 4.781.060 triệu đồng.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 117636 — **Số hiệu:** 22/2016/NQ-HĐND
**Tiêu đề:** Về kế hoạch đầu tư công năm 2017
**Vị trí trong text sạch:** [2089:2174]

```text
Tổng nguồn vốn đầu tư công năm 2017 do tỉnh quản lý là 4.781.060 triệu đồng, bao gồm:
```

**Xác minh:** verified.

## q010

**Câu hỏi:** Trong chương trình giám sát năm 2017 của Hội đồng nhân dân tỉnh Ninh Thuận, giám sát các cơ sở dạy nghề công lập giai đoạn 2011–2016 tập trung vào những mặt nào?

**Đáp án tham chiếu:** Công tác tuyển sinh, điều kiện đào tạo và hiệu quả đào tạo.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 117858 — **Số hiệu:** 53/2016/NQ-HĐND
**Tiêu đề:** Chương trình giám sát năm 2017 của Hội đồng nhân dân tỉnh
**Vị trí trong text sạch:** [2540:2726]

```text
e) Việc thực hiện chính sách, pháp luật đối với các cơ sở dạy nghề công lập trên địa bàn tỉnh Ninh Thuận giai đoạn 2011 - 2016 (công tác tuyển sinh, điều kiện đào tạo, hiệu quả đào tạo).
```

**Xác minh:** verified.

## q011

**Câu hỏi:** Theo Nghị định 05/2017/NĐ-CP, hoạt động trục vớt tài sản chìm đắm bao gồm những công việc nào?

**Đáp án tham chiếu:** Thăm dò, xây dựng và thực hiện phương án làm nổi, di dời, phá dỡ, phá hủy tài sản chìm đắm.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 118556 — **Số hiệu:** 05/2017/NĐ-CP
**Tiêu đề:** Quy định về xử lý tài sản chìm đắm trên tuyến đường thủy nội địa, vùng nước cảng biển và vùng biển Việt Nam
**Vị trí trong text sạch:** [1887:2030]

```text
4. Trục vớt tài sản chìm đắm bao gồm các hoạt động: Thăm dò, xây dựng và thực hiện phương án làm nổi, di dời, phá dỡ, phá hủy tài sản chìm đắm.
```

**Xác minh:** verified.

## q012

**Câu hỏi:** Theo Nghị quyết 27/NQ-CP về quản lý tài nguyên và môi trường, bộ nào chủ trì và phối hợp với bộ nào để hướng dẫn giải phóng mặt bằng công trình giao thông và đất hành lang an toàn đường bộ?

**Đáp án tham chiếu:** Bộ Tài nguyên và Môi trường chủ trì, phối hợp với Bộ Giao thông vận tải.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 11901 — **Số hiệu:** 27/NQ-CP
**Tiêu đề:** Về một số giải pháp cấp bách trong công tác quản lý nhà nước về tài nguyên và môi trường
**Vị trí trong text sạch:** [1219:1731]

```text
1. Bộ Tài nguyên và Môi trường có trách nhiệm:
a) Chủ trì, phối hợp với các Bộ, ngành có liên quan và các địa phương tổ chức thực hiện Ðề án tạo quỹ đất của Nhà nước phục vụ các mục tiêu công ích, chính sách xã hội, điều tiết thị trường đất đai và hỗ trợ tái định cư sau khi được cấp có thẩm quyền phê duyệt;
b) Chủ trì, phối hợp với Bộ Giao thông vận tải hướng dẫn cụ thể việc giải phóng mặt bằng cho các dự án đầu tư xây dựng công trình giao thông và đất hành lang an toàn đường bộ theo quy định của pháp luật.
```

**Xác minh:** verified.

## q013

**Câu hỏi:** Theo Nghị định 15/2017/NĐ-CP, nhiệm vụ về quy chuẩn và quy trình sản xuất muối của Bộ Nông nghiệp và Phát triển nông thôn có bao gồm muối dùng trong y tế không?

**Đáp án tham chiếu:** Không. Quy định loại trừ muối dùng trong lĩnh vực y tế.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 119066 — **Số hiệu:** 15/2017/NĐ-CP
**Tiêu đề:** Quy định chức năng, nhiệm vụ, quyền hạn và cơ cấu tổ chức của Bộ Nông nghiệp và Phát triển nông thôn
**Vị trí trong text sạch:** [6303:6483]

```text
b) Ban hành và kiểm tra thực hiện quy chuẩn kỹ thuật quốc gia, quy trình về sản xuất, chế biến bảo quản muối và các sản phẩm của muối (không bao gồm muối dùng trong lĩnh vực y tế).
```

**Xác minh:** verified.

## q014

**Câu hỏi:** Theo Luật Thi hành án hình sự năm 2019, chuẩn bị tái hòa nhập cộng đồng cho phạm nhân gồm những nội dung nào? Theo Thông tư của Bộ Công an năm 2013 về giáo dục và tư vấn cho phạm nhân sắp chấp hành xong án phạt tù, nội dung giáo dục về hòa nhập cộng đồng có những kỹ năng nào?

**Đáp án tham chiếu:** Luật năm 2019 nêu: tư vấn tâm lý, hỗ trợ thủ tục pháp lý; định hướng nghề nghiệp, tìm kiếm việc làm; hỗ trợ một phần kinh phí từ Quỹ hòa nhập cộng đồng của trại giam. Thông tư năm 2013 nêu giáo dục về hòa nhập cộng đồng và các kỹ năng tìm kiếm việc làm, ổn định cuộc sống, khắc phục khó khăn, thách thức, từ chối rủ rê, lôi kéo của đối tượng xấu và phòng tránh tệ nạn xã hội.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 162690 — **Số hiệu:** 41/2019/QH14
**Tiêu đề:** Thi hành án hình sự
**Vị trí trong text sạch:** [83283:83719]

```text
1. Trại giam, trại tạm giam, cơ quan thi hành án hình sự Công an cấp huyện có trách nhiệm tổ chức chuẩn bị tái hòa nhập cộng đồng trước khi phạm nhân chấp hành xong án phạt tù, được đặc xá, tha tù trước thời hạn có điều kiện. Nội dung chuẩn bị tái hòa nhập cộng đồng bao gồm:
a) Tư vấn tâm lý, hỗ trợ các thủ tục pháp lý;
b) Định hướng nghề nghiệp, tìm kiếm việc làm;
c) Hỗ trợ một phần kinh phí từ Quỹ hòa nhập cộng đồng của trại giam.
```

### Bằng chứng 2

**doc_id:** 44394 — **Số hiệu:** 39/2013/TT-BCA
**Tiêu đề:** Quy định về giáo dục và tư vấn cho phạm nhân 
sắp chấp hành xong án phạt tù
**Vị trí trong text sạch:** [5781:5991]

```text
d) Giáo dục về hòa nhập cộng đồng; kỹ năng tìm kiếm việc làm, ổn định cuộc sống, khắc phục khó khăn, thách thức của cuộc sống, từ chối việc rủ rê, lôi kéo của các đối tượng xấu và phòng tránh các tệ nạn xã hội.
```

**Xác minh:** verified.

## q015

**Câu hỏi:** Theo Nghị quyết 35/2017/QH14, Đoàn đại biểu Quốc hội và đại biểu Quốc hội xây dựng nội dung giám sát dựa trên căn cứ nào?

**Đáp án tham chiếu:** Căn cứ điều kiện và tình hình thực tế, chủ động lựa chọn nội dung để xây dựng chương trình, phối hợp và tiến hành giám sát, báo cáo kết quả theo pháp luật.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 122859 — **Số hiệu:** 35/2017/QH14
**Tiêu đề:** Về chương trình giám sát của Quốc hội năm 2018
**Vị trí trong text sạch:** [3958:4178]

```text
Đoàn đại biểu Quốc hội, đại biểu Quốc hội căn cứ điều kiện và tình hình thực tế, chủ động lựa chọn nội dung để xây dựng chương trình, phối hợp và tiến hành hoạt động giám sát, báo cáo kết quả theo quy định của pháp luật.
```

**Xác minh:** verified.

## q016

**Câu hỏi:** Theo khoản 1 Điều 7 Luật Trách nhiệm bồi thường của Nhà nước năm 2017, ba căn cứ phải đồng thời có để Nhà nước chịu trách nhiệm bồi thường là gì?

**Đáp án tham chiếu:** Có một trong các căn cứ xác định hành vi trái pháp luật của người thi hành công vụ gây thiệt hại và yêu cầu bồi thường tương ứng theo khoản 2 Điều 7; có thiệt hại thực tế thuộc phạm vi trách nhiệm bồi thường của Nhà nước; có mối quan hệ nhân quả giữa thiệt hại thực tế và hành vi gây thiệt hại.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 122863 — **Số hiệu:** 10/2017/QH14
**Tiêu đề:** Trách nhiệm bồi thường của nhà nước
**Vị trí trong text sạch:** [6293:6724]

```text
1. Nhà nước có trách nhiệm bồi thường khi có đủ các căn cứ sau đây:
a) Có một trong các căn cứ xác định hành vi trái pháp luật của người thi hành công vụ gây thiệt hại và yêu cầu bồi thường tương ứng quy định tại khoản 2 Điều này;
b) Có thiệt hại thực tế của người bị thiệt hại thuộc phạm vi trách nhiệm bồi thường của Nhà nước theo quy định của Luật này;
c) Có mối quan hệ nhân quả giữa thiệt hại thực tế và hành vi gây thiệt hại.
```

**Xác minh:** verified.

## q017

**Câu hỏi:** Theo nghị định điều chỉnh địa giới để thành lập huyện Mỏ Cày Bắc thuộc tỉnh Bến Tre năm 2009, phần còn lại của xã Hưng Khánh Trung sau điều chỉnh được đổi tên thành gì?

**Đáp án tham chiếu:** Xã Hưng Khánh Trung B.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 12305 — **Số hiệu:** 08/NĐ-CP
**Tiêu đề:** Về việc điều chỉnh địa giới hành chính xã, phường để thành lập xã, phường thuộc huyện Mỏ Cày, huyện Chợ Lách, thị xã Bến Tre; điều chỉnh địa giới hành chính huyện Mỏ Cày, huyện Chợ Lách để thành lập huyện mỏ Cày Bắc thuộc tỉnh Bến Tre
**Vị trí trong text sạch:** [3677:3800]

```text
- Xã Hưng Khánh Trung còn lại 1.024,03 ha diện tích tự nhiên và 7.334 nhân khẩu (được đổi tên thành xã Hưng Khánh Trung B).
```

**Xác minh:** verified.

## q018

**Câu hỏi:** Theo Quyết định 05/2017/QĐ-TTg, cơ quan nào đảm nhiệm chức năng Ban Chỉ đạo quốc gia về ứng cứu khẩn cấp bảo đảm an toàn thông tin mạng?

**Đáp án tham chiếu:** Ban Chỉ đạo an toàn thông tin quốc gia.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 123054 — **Số hiệu:** 05/2017/QĐ-TTg
**Tiêu đề:** Ban hành quy định về hệ thống phương án ứng cứu khẩn cấp bảo đảm an toàn thông tin mạng quốc gia
**Vị trí trong text sạch:** [1311:1483]

```text
1. Ban Chỉ đạo an toàn thông tin quốc gia đảm nhiệm chức năng Ban Chỉ đạo quốc gia về ứng cứu khẩn cấp bảo đảm an toàn thông tin mạng (sau đây gọi là Ban Chỉ đạo quốc gia).
```

**Xác minh:** verified.

## q019

**Câu hỏi:** Theo Thông tư 524/1999/TT-BQP, Thủ trưởng Bộ, ngành, Chủ tịch UBND tỉnh hoặc người được ủy quyền phải ghi nhận việc nhận quyết định và lệnh huy động lực lượng dự bị động viên như thế nào?

**Đáp án tham chiếu:** Ghi rõ thời gian nhận được quyết định huy động, lệnh huy động và ký tên.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 124009 — **Số hiệu:** 524/1999/TT-BQP
**Tiêu đề:** Hướng dẫn thực hiện việc thông báo Quyết định huy động và lệnh huy động, tập trung, vận chuyển, giao nhận lực lượng Dự bị động viên
**Vị trí trong text sạch:** [1576:2005]

```text
- Thủ trưởng Bộ, ngành, Chủ tịch UBND tỉnh (hoặc người được ủy quyền) tiến hành:
+ Ra lệnh mở phong bì (trong đó có lệnh huy động lực lượng DBĐV đã được chuẩn bị sẵn) có ký hiệu ứng với tín hiệu của điện thông báo và ghi ngày, tháng, năm theo điện vào lệnh đó.
- Trực tiếp nghiên cứu nắm vững nội dung quyết định huy động và lệnh huy động lực lượng DBĐV.
+ Ghi rõ thời gian nhận được quyết định huy động, lệnh huy động và ký
tên.
```

**Xác minh:** verified.

## q020

**Câu hỏi:** Theo Nghị quyết 31/2008/NQ-CP về quy hoạch sử dụng đất Long An, nếu phải điều chỉnh các chỉ tiêu chủ yếu thì UBND tỉnh phải trình ai xem xét, quyết định?

**Đáp án tham chiếu:** Trình Chính phủ xem xét, quyết định.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 12443 — **Số hiệu:** 31/2008/NQ-CP
**Tiêu đề:** Về việc xét duyệt điều chỉnh quy hoạch sử dụng đất đến năm 2010 và kế hoạch sử dụng đất kỳ cuối của tỉnh Long An
**Vị trí trong text sạch:** [10442:10604]

```text
5. Trong trường hợp phải điều chỉnh các chỉ tiêu chủ yếu của quy hoạch, kế hoạch sử dụng đất thì Ủy ban nhân dân tỉnh Long An trình Chính phủ xem xét, quyết định.
```

**Xác minh:** verified.

## q021

**Câu hỏi:** Theo Luật Tiếp cận thông tin số 104/2016/QH13, Nhà nước tạo thuận lợi tiếp cận thông tin cho những nhóm người nào? Theo Nghị định 13/2018/NĐ-CP, cơ quan cung cấp thông tin phải giúp đỡ ra sao khi người khuyết tật gặp khó khăn trong việc điền, ký Phiếu yêu cầu hoặc tiếp cận thông tin?

**Đáp án tham chiếu:** Luật nêu người khuyết tật và người sinh sống ở khu vực biên giới, hải đảo, miền núi, vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn. Nghị định yêu cầu cơ quan cung cấp thông tin bố trí cán bộ, công chức hướng dẫn, giải thích và giúp đỡ người khuyết tật gặp khó khăn khi điền, ký Phiếu yêu cầu cung cấp thông tin hoặc tiếp cận thông tin.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 101873 — **Số hiệu:** 104/2016/QH13
**Tiêu đề:** Tiếp cận thông tin
**Vị trí trong text sạch:** [1905:2106]

```text
6. Nhà nước tạo điều kiện thuận lợi để người khuyết tật, người sinh sống ở khu vực biên giới, hải đảo, miền núi, vùng có điều kiện kinh tế - xã hội đặc biệt khó khăn thực hiện quyền tiếp cận thông tin.
```

### Bằng chứng 2

**doc_id:** 127607 — **Số hiệu:** 13/2018/NĐ-CP
**Tiêu đề:** Quy định chi tiết và biện pháp thi hành 
Luật tiếp cận thông tin
**Vị trí trong text sạch:** [4867:5088]

```text
4. Cơ quan cung cấp thông tin bố trí cán bộ, công chức hướng dẫn, giải thích và giúp đỡ người khuyết tật gặp khó khăn trong việc điền Phiếu, ký Phiếu yêu cầu cung cấp thông tin hoặc khó khăn trong việc tiếp cận thông tin.
```

**Xác minh:** verified.

## q022

**Câu hỏi:** Theo Điều 1 Nghị định 19/2008/NĐ-CP, chế độ phụ cấp trách nhiệm phòng, chống tham nhũng áp dụng cho những nhóm đối tượng nào?

**Đáp án tham chiếu:** Thành viên Ban Chỉ đạo về phòng, chống tham nhũng ở Trung ương và cấp tỉnh; cán bộ, công chức, viên chức thuộc biên chế hoạt động chuyên trách của Văn phòng Ban Chỉ đạo ở Trung ương và bộ phận giúp việc Ban Chỉ đạo cấp tỉnh.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 12794 — **Số hiệu:** 19/2008/NĐ-CP
**Tiêu đề:** Quy định chế độ phụ cấp trách nhiệm trong hoạt động phòng, chống tham nhũng
**Vị trí trong text sạch:** [875:1495]

```text
Nghị định này quy định chế độ phụ cấp trách nhiệm trong hoạt động phòng, chống tham nhũng áp dụng đối với các đối tượng sau:
1. Thành viên Ban Chỉ đạo về phòng, chống tham nhũng ở Trung ương và ở tỉnh, thành phố trực thuộc Trung ương (sau đây viết tắt là thành viên Ban Chỉ đạo).
2. Cán bộ, công chức, viên chức thuộc biên chế hoạt động chuyên trách của Văn phòng Ban Chỉ đạo về phòng, chống tham nhũng ở Trung ương và của bộ phận giúp việc Ban Chỉ đạo tỉnh, thành phố trực thuộc Trung ương về phòng, chống tham nhưng (sau đây gọi chung là Văn phòng Ban Chỉ đạo ở Trung ương và bộ phận giúp việc Ban Chỉ đạo ở cấp tỉnh).
```

**Xác minh:** verified.

## q023

**Câu hỏi:** So sánh quy định được ghi trong Luật sửa đổi số 16/2008/QH12 và Luật Phòng, chống ma túy số 73/2021/QH14: văn bản năm 2008 quy định thời gian quản lý sau cai nghiện đối với người chấp hành xong cai nghiện bắt buộc là bao lâu, và khoản 2 Điều 40 của Luật năm 2021 quy định thời hạn nào cho người chấp hành xong quyết định áp dụng biện pháp xử lý hành chính đưa vào cơ sở cai nghiện bắt buộc?

**Đáp án tham chiếu:** Theo nội dung sửa đổi Điều 33 trong văn bản năm 2008, người chấp hành xong thời gian cai nghiện bắt buộc tại cơ sở cai nghiện chịu quản lý sau cai nghiện từ một năm đến hai năm. Theo khoản 2 Điều 40 Luật năm 2021, người chấp hành xong quyết định áp dụng biện pháp xử lý hành chính đưa vào cơ sở cai nghiện bắt buộc chịu quản lý sau cai nghiện trong 02 năm kể từ ngày chấp hành xong quyết định. Đây là đối chiếu nội dung hai phiên bản, không kết luận cả hai đồng thời áp dụng.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 12802 — **Số hiệu:** 16/2008/QH12
**Tiêu đề:** Sửa đổi, bổ sung một số điều của Luật Phòng, chống ma túy
**Vị trí trong text sạch:** [6626:6826]

```text
1. Người nghiện ma túy sau khi chấp hành xong thời gian cai nghiện ma túy bắt buộc tại cơ sở cai nghiện phải chịu sự quản lý sau cai nghiện từ một năm đến hai năm theo một trong hai hình thức sau đây:
```

### Bằng chứng 2

**doc_id:** 152501 — **Số hiệu:** 73/2021/QH14
**Tiêu đề:** Luật Phòng, chống ma túy
**Vị trí trong text sạch:** [44110:44314]

```text
2. Người đã chấp hành xong quyết định áp dụng biện pháp xử lý hành chính đưa vào cơ sở cai nghiện bắt buộc chịu sự quản lý sau cai nghiện ma túy trong thời hạn 02 năm kể từ ngày chấp hành xong quyết định.
```

**Xác minh:** verified.

## q024

**Câu hỏi:** Theo Luật Cạnh tranh năm 2018, tác động hạn chế cạnh tranh được hiểu như thế nào?

**Đáp án tham chiếu:** Tác động loại trừ, làm giảm, sai lệch hoặc cản trở cạnh tranh trên thị trường.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 133401 — **Số hiệu:** 23/2018/QH14
**Tiêu đề:** Cạnh tranh
**Vị trí trong text sạch:** [1256:1368]

```text
3. Tác động hạn chế cạnh tranh là tác động loại trừ, làm giảm, sai lệch hoặc cản trở cạnh tranh trên thị trường.
```

**Xác minh:** verified.

## q025

**Câu hỏi:** Theo Luật Cảnh sát biển Việt Nam năm 2018, cán bộ, chiến sĩ Cảnh sát biển có bao gồm công nhân và viên chức không?

**Đáp án tham chiếu:** Có. Bao gồm sĩ quan, quân nhân chuyên nghiệp, hạ sĩ quan, binh sĩ, công nhân và viên chức thuộc biên chế Cảnh sát biển Việt Nam.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 136051 — **Số hiệu:** 33/2018/QH14
**Tiêu đề:** Cảnh sát biển Việt Nam
**Vị trí trong text sạch:** [803:970]

```text
2. Cán bộ, chiến sĩ Cảnh sát biển Việt Nam bao gồm sĩ quan, quân nhân chuyên nghiệp, hạ sĩ quan, binh sĩ, công nhân và viên chức thuộc biên chế Cảnh sát biển Việt Nam.
```

**Xác minh:** verified.

## q026

**Câu hỏi:** Theo Luật Chăn nuôi năm 2018, một đơn vị vật nuôi tương đương bao nhiêu kg khối lượng sống và mật độ chăn nuôi được tính như thế nào? Theo quyết định của tỉnh Lâm Đồng về mật độ chăn nuôi đến năm 2030, mức mật độ tối đa của tỉnh là bao nhiêu?

**Đáp án tham chiếu:** Theo Luật Chăn nuôi năm 2018, mỗi đơn vị vật nuôi tương đương 500 kg khối lượng vật nuôi sống; mật độ chăn nuôi bằng tổng số đơn vị vật nuôi trên 01 ha đất nông nghiệp. Theo quyết định của Lâm Đồng về mật độ đến năm 2030, mật độ không vượt quá 01 đơn vị vật nuôi trên 01 ha đất nông nghiệp.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 137311 — **Số hiệu:** 32/2018/QH14
**Tiêu đề:** Chăn nuôi
**Vị trí trong text sạch:** [61656:61937]

```text
1. Đơn vị vật nuôi là đơn vị quy đổi của gia súc, gia cầm theo khối lượng sống, không phụ thuộc vào giống, tuổi và giới tính. Mỗi đơn vị vật nuôi tương đương với 500 kg khối lượng vật nuôi sống.
2. Mật độ chăn nuôi được tính bằng tổng số đơn vị vật nuôi trên 01 ha đất nông nghiệp.
```

### Bằng chứng 2

**doc_id:** 187355 — **Số hiệu:** 14/2026/QĐ-UBND
**Tiêu đề:** Quy định mật độ chăn nuôi trên địa bàn tỉnh Lâm Đồng đến năm 2030
**Vị trí trong text sạch:** [1252:1388]

```text
Mật độ chăn nuôi trên địa bàn tỉnh Lâm Đồng đến năm 2030 không vượt quá 01 đơn vị vật nuôi (viết tắt là ĐVN) trên 01 ha đất nông nghiệp.
```

**Xác minh:** verified.

## q027

**Câu hỏi:** Theo Nghị quyết 01/2020/NQ-HĐTP, người không phải thành viên dòng họ có thể là bị đơn trong tranh chấp tài sản chung của dòng họ không?

**Đáp án tham chiếu:** Có, nếu người đó là người bị kiện và có quyền, nghĩa vụ liên quan đến tài sản chung của dòng họ.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 141135 — **Số hiệu:** 01/2020/NQ-HĐTP
**Tiêu đề:** Hướng dẫn áp dụng một số quy định của pháp luật trong giải quyết tranh chấp về tài sản chung của dòng họ
**Vị trí trong text sạch:** [1812:2037]

```text
2. Bị đơn trong vụ án tranh chấp về tài sản chung của dòng họ là người bị kiện. Bị đơn có thể là thành viên dòng họ hoặc người không phải là thành viên dòng họ nhưng có quyền, nghĩa vụ liên quan đến tài sản chung của dòng họ.
```

**Xác minh:** verified.

## q028

**Câu hỏi:** Theo Luật Thi hành án hình sự năm 2019, phạm nhân có quyền đề nghị xét đặc xá không? Theo Luật Đặc xá năm 2018, ai quyết định thành lập Hội đồng tư vấn đặc xá?

**Đáp án tham chiếu:** Luật Thi hành án hình sự năm 2019 ghi nhận phạm nhân được đề nghị xét đặc xá theo quy định của pháp luật. Theo Luật Đặc xá năm 2018, Chủ tịch nước quyết định thành lập Hội đồng tư vấn đặc xá.

**Số văn bản cần thiết:** 2

### Bằng chứng 1

**doc_id:** 162690 — **Số hiệu:** 41/2019/QH14
**Tiêu đề:** Thi hành án hình sự
**Vị trí trong text sạch:** [48269:48384]

```text
g) Được bảo đảm quyền khiếu nại, tố cáo; được đề nghị xét đặc xá, bồi thường thiệt hại theo quy định của pháp luật;
```

### Bằng chứng 2

**doc_id:** 141383 — **Số hiệu:** 30/2018/QH14
**Tiêu đề:** Luật Đặc xá
**Vị trí trong text sạch:** [4669:4758]

```text
1. Khi có Quyết định về đặc xá, Chủ tịch nước quyết định thành lập Hội đồng tư vấn đặc xá
```

### Bằng chứng 3 — thay thế bằng chứng 2 cho ý về thẩm quyền

**doc_id:** 141383 — **Số hiệu:** 30/2018/QH14
**Tiêu đề:** Luật Đặc xá
**Vị trí trong text sạch:** [1395:1662]

```text
4. Hội đồng tư vấn đặc xá là tổ chức liên ngành bao gồm đại diện lãnh đạo các cơ quan, tổ chức có liên quan do Chủ tịch nước quyết định thành lập để triển khai thực hiện Quyết định về đặc xá và tham mưu, tư vấn cho Chủ tịch nước trong việc thực hiện hoạt động đặc xá.
```

**Xác minh:** verified.

## q029

**Câu hỏi:** Theo Luật Bảo vệ bí mật nhà nước năm 2018, lộ bí mật nhà nước khác mất bí mật nhà nước như thế nào?

**Đáp án tham chiếu:** Lộ bí mật là người không có trách nhiệm biết được bí mật nhà nước. Mất bí mật là tài liệu, vật chứa bí mật không còn thuộc sự quản lý của cơ quan, tổ chức, cá nhân có trách nhiệm quản lý.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 141824 — **Số hiệu:** 29/2018/QH14
**Tiêu đề:** Luật Bảo vệ bí mật nhà nước
**Vị trí trong text sạch:** [880:1122]

```text
3. Lộ bí mật nhà nước là trường hợp người không có trách nhiệm biết được bí mật nhà nước.
4. Mất bí mật nhà nước là trường hợp tài liệu, vật chứa bí mật nhà nước không còn thuộc sự quản lý của cơ quan, tổ chức, cá nhân có trách nhiệm quản lý.
```

**Xác minh:** verified.

## q030

**Câu hỏi:** Theo Thông tư 11/2020/TT-BCT về xuất xứ EVFTA, nhà xuất khẩu có nhất thiết phải là người bán hàng phát hành hóa đơn cho lô hàng không?

**Đáp án tham chiếu:** Không. Nhà xuất khẩu không nhất thiết là người bán hàng phát hành hóa đơn; người bán hàng được phép đặt trụ sở tại lãnh thổ nước không phải thành viên EVFTA.

**Số văn bản cần thiết:** 1

### Bằng chứng 1

**doc_id:** 142645 — **Số hiệu:** 11/2020/TT-BCT
**Tiêu đề:** Quy định Quy tắc xuất xứ hàng hóa trong Hiệp định Thương mại tự do giữa Việt Nam và Liên minh châu Âu
**Vị trí trong text sạch:** [2314:2504]

```text
Nhà xuất khẩu không nhất thiết là người bán hàng mà phát hành hóa đơn cho lô hàng (hóa đơn bên thứ ba). Người bán hàng được phép đặt trụ sở tại lãnh thổ của nước không phải thành viên EVFTA.
```

**Xác minh:** verified.
