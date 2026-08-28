# ComfyUI + Model Dashboard + JupyterLab — Vast.ai Template (Krea 2)

Docker template สำหรับ [Vast.ai](https://cloud.vast.ai) ที่เปิด 3 บริการพร้อมกัน

| พอร์ต | บริการ | ใช้ทำอะไร |
|---|---|---|
| **8188/tcp** | **ComfyUI** | หน้าหลักสำหรับ gen ภาพ |
| **8189/tcp** | **Model Dashboard** | วางลิงก์ Civitai / Hugging Face + API key แล้วกดโหลด LoRA/โมเดล |
| **8888/tcp** | **JupyterLab** | เทอร์มินัล + โน้ตบุ๊ก จัดการไฟล์บนเครื่อง |

ปรับจูนมาสำหรับ **Krea 2 / Krea 2 Turbo** (12.9B DiT, ComfyUI รองรับ native ตั้งแต่ v0.26.0)
บน CUDA 12.8 ขึ้นไป — ค่าเริ่มต้นคือ **CUDA 12.9 + PyTorch 2.13** ซึ่งรันได้ทั้ง RTX 4090 และ RTX 5090 (Blackwell)

---

## เริ่มเร็ว 3 ขั้น

```bash
DOCKER_USER=yourdockerhubname ./build.sh
```

จากนั้นสร้าง Template บน Vast.ai ตาม [`docs/DEPLOY.md`](docs/DEPLOY.md) แล้วเช่าเครื่อง
ทุกอย่างขึ้นเอง รวมถึงดาวน์โหลดชุด Krea 2 Turbo (~17.4 GiB / 18.6 GB) ให้อัตโนมัติในเบื้องหลัง

---

## โครงสร้าง

```
vast-comfyui-krea2/
├── Dockerfile                  # base CUDA 12.9 + torch 2.13 + ComfyUI + Manager
├── build.sh                    # build/push หลาย CUDA variant
├── docker-compose.yml          # ไว้ทดสอบบนเครื่องตัวเอง
├── supervisor/supervisord.conf # คุม 3 service + sshd (ออปชัน)
├── scripts/
│   ├── entrypoint.sh           # เตรียม /workspace, โทเคน, provisioning
│   ├── env.sh                  # env ร่วมของทุก service
│   ├── start-comfyui.sh
│   ├── start-dashboard.sh
│   ├── start-jupyter.sh
│   ├── start-sshd.sh
│   ├── modelctl.py             # CLI คุม dashboard (`modelctl`)
│   └── provisioning-example.sh # ตัวอย่าง PROVISIONING_SCRIPT
├── dashboard/                  # FastAPI + หน้าเว็บ (พอร์ต 8189)
│   ├── app.py  core.py  resolvers.py  downloader.py
│   ├── catalog.json            # รายการโมเดล 1-click
│   └── static/index.html  static/login.html
└── docs/
    ├── DEPLOY.md               # วิธี deploy บน Vast.ai แบบละเอียด
    └── USAGE.md                # วิธีใช้งาน + workflow Krea 2
```

---

## Environment variables

| ตัวแปร | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `DASHBOARD_TOKEN` | สุ่มตอนบูตครั้งแรก | รหัสเข้า Dashboard 8189 |
| `JUPYTER_TOKEN` | สุ่มตอนบูตครั้งแรก | โทเคน JupyterLab 8888 |
| `AUTO_INSTALL` | `krea2-turbo` | ชุดที่โหลดอัตโนมัติตอนบูตครั้งแรก ใส่ `none` เพื่อปิด |
| `CIVITAI_TOKEN` | — | เติมคีย์ Civitai ให้ล่วงหน้า (ใส่ใน UI ทีหลังก็ได้) |
| `HF_TOKEN` | — | เติม Hugging Face token ให้ล่วงหน้า |
| `COMFY_ARGS` | — | แฟล็กเสริมของ ComfyUI เช่น `--lowvram --reserve-vram 1.5` |
| `COMFY_FAST` | `1` | เปิด `--fast` (fp16 accumulation) ตั้ง `0` เพื่อปิด |
| `DOWNLOAD_CONCURRENCY` | `2` | โหลดพร้อมกันกี่ไฟล์ |
| `DATA_DIR` | `/workspace` | ที่เก็บโมเดล/ผลลัพธ์ทั้งหมด |
| `PUBLIC_KEY` | — | ใส่ ssh public key แล้ว sshd จะเปิดที่พอร์ต 22 |
| `PROVISIONING_SCRIPT` | — | URL ของสคริปต์ที่จะรันตอนบูต (ลง custom node เพิ่ม) |

ค่าที่ `AUTO_INSTALL` รับได้: `krea2-turbo` · `krea2-turbo-nvfp4` · `krea2-turbo-bf16` ·
`krea2-raw` · `krea2-style-ref` · `krea2-styles` · `upscalers` · `none`
(ใส่หลายค่าคั่นด้วยคอมมาได้ เช่น `krea2-turbo,upscalers`)

---

## ข้อมูลโมเดล Krea 2

โหลดจาก [`Comfy-Org/Krea-2`](https://huggingface.co/Comfy-Org/Krea-2) — ไม่ต้องใช้ token

| ไฟล์ | โฟลเดอร์ | ขนาด | หมายเหตุ |
|---|---|---|---|
| `krea2_turbo_fp8_scaled.safetensors` | `diffusion_models` | 13.14 GB | **แนะนำ** 8 steps |
| `krea2_turbo_nvfp4.safetensors` | `diffusion_models` | 7.67 GB | RTX 50xx เท่านั้น |
| `krea2_raw_fp8_scaled.safetensors` | `diffusion_models` | 13.14 GB | 52 steps คุณภาพสูงสุด |
| `qwen3vl_4b_fp8_scaled.safetensors` | `text_encoders` | 5.24 GB | **จำเป็น** |
| `qwen_image_vae.safetensors` | `vae` | 0.25 GB | **จำเป็น** |
| `krea2_style_reference.safetensors` | `loras` | 0.46 GB | สำหรับ style reference |

---

## ความปลอดภัย

- **8189 (Dashboard)** และ **8888 (Jupyter)** ป้องกันด้วยโทเคน — ดูโทเคนได้จาก Instance Logs
- **8188 (ComfyUI)** เปิดตรงไม่มีรหัส เหมือน template ComfyUI ทั่วไปบน Vast
  ใครรู้ IP:port ก็เข้าได้ ถ้าต้องการปิด ให้ตั้ง `COMFY_ARGS="--listen 127.0.0.1"`
  แล้วเข้าผ่าน SSH tunnel แทน (`ssh -L 8188:localhost:8188 ...`)
- API key ของ Civitai/HF เก็บที่ `/workspace/.config/modelhub/keys.json` สิทธิ์ `600`
  อยู่บนดิสก์ instance เท่านั้น ส่งออกเฉพาะตอนดาวน์โหลดไปยัง civitai.com / huggingface.co
- **อย่าลืมว่า instance บน Vast เป็นเครื่องของคนอื่น** — ไม่ควรใส่คีย์ที่มีสิทธิ์เขียน
  ใช้ Civitai key แบบ read และ HF token แบบ `read` เท่านั้น

---

## เอกสารต่อ

- [`docs/DEPLOY.md`](docs/DEPLOY.md) — build image, สร้าง template, เช่าเครื่อง, หา URL/โทเคน
- [`docs/USAGE.md`](docs/USAGE.md) — ใช้ Dashboard, workflow Krea 2, `modelctl`, แก้ปัญหา

อ้างอิง: [ComfyUI Krea 2 tutorial](https://docs.comfy.org/tutorials/image/krea/krea-2) ·
[Krea 2 open source](https://www.krea.ai/krea-2-open-source) ·
[Vast.ai templates](https://docs.vast.ai/instances/templates)
