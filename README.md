# File Validator — Backend (FastAPI)

## Struktur Project
```
backend/
├── app/
│   ├── core/
│   │   ├── auth.py        # JWT authentication
│   │   └── config.py      # Settings & konfigurasi
│   ├── routers/
│   │   ├── auth.py        # Endpoint login
│   │   └── validation.py  # 6 endpoint validasi + 3 upload
│   ├── validators/
│   │   ├── price.py       # Logika validasi File Price
│   │   ├── inventory.py   # Logika validasi File Inventory
│   │   └── master.py      # Logika validasi File Master Product
│   └── main.py            # Entry point FastAPI
├── inbox/                 # Taruh file klien yang belum diproses di sini
├── error/                 # Taruh file klien yang gagal diproses di sini
├── requirements.txt
└── .env                   # Konfigurasi environment

```

## Cara Menjalankan

### 1. Buat virtual environment
```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Jalankan server
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Buka dokumentasi API (Swagger)
```
http://localhost:8000/docs
```

---

## Default Login
- **Email:** admin@company.com
- **Password:** admin123

> Ganti password di `app/core/auth.py` > `USERS_DB` sebelum deploy ke production.

---

## Endpoint API

### Auth
| Method | Endpoint | Keterangan |
|--------|----------|------------|
| POST | `/auth/login` | Login, dapat token JWT |
| GET | `/auth/me` | Info user yang sedang login |

### Validasi Folder (Postman)
| Method | Endpoint | Body |
|--------|----------|------|
| POST | `/validate/inbox/price` | `{"filename": ""}` atau `{"filename": "namafile.txt"}` |
| POST | `/validate/error/price` | sama |
| POST | `/validate/inbox/inventory` | sama |
| POST | `/validate/error/inventory` | sama |
| POST | `/validate/inbox/master-product` | sama |
| POST | `/validate/error/master-product` | sama |

### Upload & Validasi (Web)
| Method | Endpoint | Keterangan |
|--------|----------|------------|
| POST | `/validate/upload/price` | Upload file .txt langsung |
| POST | `/validate/upload/inventory` | Upload file .txt langsung |
| POST | `/validate/upload/master-product` | Upload file .txt langsung |

---

## Contoh Response
```json
{
  "summary": {
    "total_files": 2,
    "valid_files": 1,
    "invalid_files": 1,
    "total_errors": 3
  },
  "results": [
    {
      "file": "price_0100.txt",
      "folder": "inbox",
      "valid": false,
      "total_rows": 13,
      "errors": [
        {
          "row": 5,
          "column": "LEGAL ENTITY CODE",
          "message": "Terdapat spasi di akhir cell. Nilai: '0100 '"
        },
        {
          "row": 12,
          "column": "LIST PRICE",
          "message": "LIST PRICE menggunakan koma sebagai desimal, seharusnya titik. Nilai: '1.599,000'"
        }
      ]
    }
  ]
}
```
