/// <reference types="vite/client" />

/**
 * Khai báo tường minh các biến VITE_* mà app đọc.
 *
 * Không có file này, `import.meta.env.VITE_API_BASE_URL` là `any`: gõ sai tên biến vẫn
 * biên dịch trót lọt rồi hỏng lúc chạy trên production — đúng loại lỗi tốn nhiều thời
 * gian nhất để tìm vì bản dev vẫn chạy bình thường.
 */
interface ImportMetaEnv {
  /**
   * URL gốc của backend, vd `https://api.vocabforge.example.com`. Không có dấu `/` cuối.
   * BẮT BUỘC ở bản build production (FE và BE deploy tách nhau nên không thể suy ra).
   * Bỏ trống ở dev để tự suy ra "cùng host đang mở, cổng 8000".
   */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
