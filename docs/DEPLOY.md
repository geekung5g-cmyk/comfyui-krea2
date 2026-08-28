# Deploy บน Vast.ai — ทีละขั้น

## 0. ต้องมีอะไรบ้าง

- บัญชี [Docker Hub](https://hub.docker.com) (ฟรี) — Vast ต้องดึง image จาก registry สาธารณะ
- เครื่องที่มี Docker สำหรับ build (Linux/WSL2/Mac)
- บัญชี Vast.ai ที่เติมเงินแล้ว

---

## 1. Build และ push image

```bash
cd vast-comfyui-krea2
DOCKER_USER=yourdockerhubname ./build.sh
```

ได้ image `yourdockerhubname/comfyui-krea2:1.0-cu129` (ประมาณ 12–15 GB, build ~20–30 นาที)

เลือก CUDA variant ได้:

```bash
DOCKER_USER=yourname VARIANT=cu128 ./build.sh   # host driver CUDA 12.8+ (กว้างสุด)
DOCKER_USER=yourname VARIANT=cu129 ./build.sh   # ค่าเริ่มต้น torch 2.13
DOCKER_USER=yourname VARIANT=cu130 ./build.sh   # เฉพาะเครื่อง CUDA 13
```

> **เรื่อง "CUDA 12.7 ขึ้นไป"** — NVIDIA ไม่เคยออก CUDA toolkit 12.7 ตัวเลขที่เห็นในตัวกรองของ Vast
> คือเวอร์ชันที่ **ไดรเวอร์ของเครื่อง host** รองรับ container ที่ build ด้วย cu129 ต้องการเครื่องที่
> รายงาน CUDA ≥ 12.9 (ไดรเวอร์ 575+) ซึ่งเป็นค่าปกติของเครื่อง RTX 5090 ทุกวันนี้
> ถ้าอยากได้ตัวเลือกเครื่องเยอะขึ้นให้ build `cu128` แล้วตั้งตัวกรองเป็น 12.8

ถ้าไม่อยาก build เอง ใช้ `docker-compose.yml` ทดสอบบนเครื่องตัวเองก่อนก็ได้:

```bash
docker compose up --build
```

---

## 2. สร้าง Template บน Vast.ai

เปิด [cloud.vast.ai](https://cloud.vast.ai) → เมนูซ้าย **Templates** → **+ New** / **Create Template**

กรอกตามนี้

| ช่อง | ค่าที่ใส่ |
|---|---|
| **Template Name** | `ComfyUI Krea 2 + Dashboard` |
| **Image Path:Tag** | `yourdockerhubname/comfyui-krea2:1.0-cu129` |
| **Launch Mode** | **Docker ENTRYPOINT** *(ห้ามเลือก Jupyter mode — image รัน Jupyter เองแล้ว)* |
| **Docker Options** | ดูด้านล่าง |
| **On-start Script** | เว้นว่าง |
| **Disk Space** | **150 GB** (ต่ำสุด 100 GB) |

### Docker Options (คัดลอกไปวางได้เลย)

```
-p 8188:8188 -p 8189:8189 -p 8888:8888 -e AUTO_INSTALL=krea2-turbo -e OPEN_BUTTON_PORT=8189
```

เพิ่มได้ตามต้องการ:

```
-e DASHBOARD_TOKEN=ตั้งรหัสเอง
-e JUPYTER_TOKEN=ตั้งรหัสเอง
-e CIVITAI_TOKEN=xxxxxxxx
-e HF_TOKEN=hf_xxxxxxxx
-e COMFY_ARGS=--reserve-vram 1.0
```

> `-p ภายใน:ภายใน` คือสิ่งที่บอก Vast ว่าให้เปิดพอร์ตพวกนี้ออกอินเทอร์เน็ต
> Vast จะแมปเป็นพอร์ตภายนอกแบบสุ่มให้ (เช่น `70.30.x.x:41234 → 8188/tcp`)

กด **Create / Save Template**

---

## 3. เลือกเครื่องแล้วเช่า

1. ไปหน้า **Search** → กด **Templates** ด้านบน แล้วเลือก template ที่เพิ่งสร้าง
2. ตั้งตัวกรองด้านซ้าย
   - **GPU** → `RTX 5090` (หรือ `RTX 4090`)
   - **Min CUDA Version** → `12.9` (ถ้า build cu128 ให้ใส่ `12.8`, cu130 ให้ใส่ `13.0`)
   - **Disk Space** → `150 GB`
   - **Inet Down** → `≥ 500 Mbps` — สำคัญมาก เพราะต้องโหลดโมเดล ~17.4 GiB (18.6 GB)
   - **Reliability** → `> 0.98`
3. เรียงตาม **$/hr** แล้วกด **RENT** ที่เครื่องที่พอใจ

> RTX 5090 (32 GB VRAM) พอสำหรับ `krea2_turbo_fp8_scaled` แบบสบาย ๆ
> RTX 4090 (24 GB) ก็รันได้ แต่ควรใส่ `-e COMFY_ARGS=--reserve-vram 1.5`

---

## 4. รอเครื่องขึ้น แล้วหา URL + โทเคน

ไปหน้า **Instances**

1. รอสถานะเปลี่ยนจาก *Loading / Scheduling* เป็น **Running** (ครั้งแรก 5–15 นาที เพราะต้องดึง image)
2. กดปุ่ม **☰ Logs** บนการ์ด instance → เลื่อนหาบล็อกนี้

```
================================================================================
  ComfyUI + Model Dashboard + JupyterLab
--------------------------------------------------------------------------------
  ComfyUI     http://70.30.x.x:41234
  Dashboard   http://70.30.x.x:41235/?token=a1b2c3...
  JupyterLab  http://70.30.x.x:41236/lab?token=d4e5f6...

  DASHBOARD_TOKEN = a1b2c3...
  JUPYTER_TOKEN   = d4e5f6...
================================================================================
```

3. หรือกดปุ่ม **IP** สีน้ำเงินบนการ์ด จะเห็นตารางแมปพอร์ต

```
70.30.x.x:41234  ->  8188/tcp     ComfyUI
70.30.x.x:41235  ->  8189/tcp     Dashboard
70.30.x.x:41236  ->  8888/tcp     JupyterLab
```

4. เปิดพอร์ตที่ตรงกับ **8188/tcp** = ComfyUI พร้อมใช้

> ครั้งแรกโมเดล Krea 2 (~17.4 GiB / 18.6 GB) จะทยอยโหลดอยู่เบื้องหลัง
> เปิด Dashboard (8189) ดูความคืบหน้าได้ ปกติ 3–8 นาทีบนเครื่องเน็ตเร็ว
> ComfyUI เปิดใช้ได้ทันทีระหว่างรอ แต่จะยังไม่เห็นโมเดลในลิสต์จนกว่าจะโหลดเสร็จ (กด Refresh ในหน้า ComfyUI)

---

## 5. ตรวจว่าพร้อมจริง

ใน Dashboard (8189) แท็บ **🖥 ระบบ & Log**

- ComfyUI = `ทำงานอยู่`
- ดิสก์เหลือพอ
- GPU ขึ้นชื่อรุ่นถูกต้อง

แท็บ **📁 ไฟล์ในเครื่อง** ควรเห็นครบ 3 ไฟล์

```
diffusion_models  krea2_turbo_fp8_scaled.safetensors   12.24 GB
text_encoders     qwen3vl_4b_fp8_scaled.safetensors     4.88 GB
vae               qwen_image_vae.safetensors             242 MB
```

(Dashboard นับแบบ GiB เหมือน `ls -h` · หน้า Hugging Face นับแบบ GB ทศนิยม
ตัวเลขจึงต่างกันเล็กน้อย ไฟล์เดียวกัน)

---

## 6. ปิดเครื่องอย่าให้เสียเงินฟรี

- **Stop** = หยุด GPU แต่ยังจ่ายค่าดิสก์ (โมเดลยังอยู่) — เหมาะถ้าจะกลับมาใช้พรุ่งนี้
- **Destroy** = ลบทิ้งหมด ไม่เสียเงินต่อ — โมเดลหายหมด ต้องโหลดใหม่

ก่อน Destroy โหลดผลงานเก็บก่อน — ใน JupyterLab เข้า `/workspace/ComfyUI/output`
คลิกขวาไฟล์ → Download หรือบีบอัดทั้งโฟลเดอร์ในเทอร์มินัล

```bash
cd /workspace/ComfyUI && zip -r /workspace/output.zip output
```

---

## ปัญหาที่เจอบ่อย

| อาการ | สาเหตุ / วิธีแก้ |
|---|---|
| Instance ค้างที่ *Loading* นาน | image 15 GB ครั้งแรกช้าเป็นปกติ เลือกเครื่อง Inet Down สูง ๆ |
| เปิดพอร์ต 8188 แล้วต่อไม่ได้ | ลืมใส่ `-p 8188:8188` ใน Docker Options |
| Dashboard ขึ้นหน้า login | ปกติ — เอา `DASHBOARD_TOKEN` จาก Logs ไปกรอก |
| ComfyUI ไม่เห็นโมเดล | ยังโหลดไม่เสร็จ หรือกด **R** / Refresh ในหน้า ComfyUI |
| `torch not compiled with CUDA` / ไม่เจอ GPU | เครื่องที่เช่ามีไดรเวอร์เก่ากว่าที่ build ไว้ — ตั้ง Min CUDA ให้ตรงกับ variant |
| ดิสก์เต็มกลางคัน | เพิ่ม Disk Space ตอนสร้าง instance เป็น 150–200 GB |
| อยาก reset ทั้งหมด | ลบ `/workspace/.config/modelhub/state.json` แล้วรีสตาร์ท instance |
