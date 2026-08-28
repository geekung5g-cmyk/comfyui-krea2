# วิธีใช้งาน

## 1. Dashboard พอร์ต 8189 — โหลดโมเดล/LoRA

เปิด `http://IP:พอร์ตที่แมปกับ8189/` → ใส่ `DASHBOARD_TOKEN` (ดูจาก Instance Logs)
หรือเปิดลิงก์ที่มี `?token=...` จาก log ตรง ๆ ก็เข้าได้เลย ไม่ต้องกรอก

### แท็บ ⬇ ดาวน์โหลดจากลิงก์ — วางลิงก์แล้วกดโหลด

**ขั้นตอน**

1. วางลิงก์ → กด **ตรวจสอบลิงก์** (หรือ Enter)
2. ระบบดึงชื่อไฟล์ ขนาด ประเภท และรูปตัวอย่างมาให้ พร้อม **เดาโฟลเดอร์ปลายทางให้อัตโนมัติ**
3. แก้ชื่อไฟล์ / เปลี่ยนโฟลเดอร์ได้ถ้าต้องการ
4. กด **เริ่มดาวน์โหลด** → ดูความคืบหน้าในตาราง "คิวดาวน์โหลด" (%, ความเร็ว, เวลาที่เหลือ)

ปิดหน้าเว็บได้เลย การโหลดทำงานต่อบนเซิร์ฟเวอร์

**รูปแบบลิงก์ที่รองรับ** (ทดสอบแล้วทุกแบบ)

| ต้นทาง | ตัวอย่าง |
|---|---|
| Civitai หน้าโมเดล | `https://civitai.com/models/1234` |
| Civitai ระบุเวอร์ชัน | `https://civitai.com/models/1234?modelVersionId=5678` |
| Civitai ลิงก์ดาวน์โหลด | `https://civitai.com/api/download/models/5678` |
| Civitai AIR urn | `urn:air:sdxl:lora:civitai:1234@5678` |
| HF หน้า repo | `https://huggingface.co/Comfy-Org/Krea-2` |
| HF ลิงก์ไฟล์ | `.../Krea-2/blob/main/loras/krea2_neondrip.safetensors` |
| HF แบบสั้น | `Comfy-Org/Krea-2` |
| HF แบบสั้น + ไฟล์ | `Comfy-Org/Krea-2:vae/qwen_image_vae.safetensors` |
| ลิงก์ตรง | `https://.../model.safetensors` |

ถ้าวางหน้า repo ของ Hugging Face จะขึ้นรายการไฟล์ทั้งหมดให้เลือก
หรือกด **โหลดทุกไฟล์ในรายการ** เพื่อโหลดทั้ง repo (ระวังขนาด!)

**การเดาโฟลเดอร์** — Civitai ใช้ประเภทจาก API (`LORA` → `loras`, `Checkpoint` → `checkpoints`,
`TextualInversion` → `embeddings`, `VAE` → `vae`, `Controlnet` → `controlnet`)
ส่วน Hugging Face ใช้ path ใน repo (`diffusion_models/` → `diffusion_models` เป็นต้น)
ถ้าเดาผิดก็เลือกใหม่ในดรอปดาวน์ได้

### แท็บ ⭐ Krea 2 / โมเดลแนะนำ — กดครั้งเดียวได้ครบชุด

| ชุด | ได้อะไร | ขนาด |
|---|---|---|
| Krea 2 Turbo (FP8) ⭐ | diffusion + text encoder + VAE | ~17.4 GB |
| Krea 2 Turbo (NVFP4) | FP4 เฉพาะ RTX 50xx — เล็ก/เร็วสุด | ~12.3 GB |
| Krea 2 Turbo (MXFP8) | MXFP8 เฉพาะ RTX 50xx — คุณภาพใกล้ bf16 | ~17.7 GB |
| Krea 2 RAW (FP8) | โมเดล 52 steps + ตัวประกอบ | ~17.4 GB |
| Krea 2 Turbo (BF16) | ความละเอียดเต็ม ต้องการ VRAM 48 GB+ | ~33.0 GB |
| Style Reference | turbo int8_convrot + style reference LoRA | ~18.1 GB |
| Style LoRA ทั้งหมด | LoRA ทางการ 9 ตัว | ~3.9 GB |
| Upscaler | 4x-UltraSharp + 4x_NMKD-Siax | ~128 MB |

ในแท็บรายการเต็มยังมี `krea2_raw_int8_convrot`, `krea2_raw_bf16` และ
`krea2_turbo_lora_rank_64_bf16` (LoRA ที่แปลง RAW → Turbo) ให้เลือกทีละตัวด้วย
รวมแล้วครบทั้ง **8 diffusion + 2 text encoder + 1 VAE + 11 LoRA** ตามที่มีบน
[Comfy-Org/Krea-2](https://huggingface.co/Comfy-Org/Krea-2/tree/main)

ไฟล์ที่มีอยู่แล้วจะขึ้นป้าย **ติดตั้งแล้ว** และถูกข้ามอัตโนมัติ

### แท็บ 🔑 API Keys

| ที่ไหน | เอามาจาก | จำเป็นเมื่อไหร่ |
|---|---|---|
| Civitai | [civitai.com/user/account](https://civitai.com/user/account) → API Keys | **เกือบทุกครั้ง** — Civitai บังคับล็อกอินสำหรับการดาวน์โหลดส่วนใหญ่ |
| Hugging Face | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (สิทธิ์ `read`) | เฉพาะ repo ที่ gated/private (Krea 2 ไม่ต้องใช้) |

กด **บันทึก** แล้วกด **ทดสอบ** เพื่อยืนยันว่าคีย์ใช้ได้จริง
คีย์เก็บที่ `/workspace/.config/modelhub/keys.json` สิทธิ์ `600` · ลบได้โดยบันทึกค่าว่าง

### แท็บ 📁 ไฟล์ในเครื่อง
ดู/กรอง/ค้นหา/ลบไฟล์โมเดลทั้งหมด พร้อมขนาดรวม — ใช้เคลียร์พื้นที่ตอนดิสก์ใกล้เต็ม

### แท็บ 🖥 ระบบ & Log
สถานะ ComfyUI, GPU, ดิสก์, ปุ่มรีสตาร์ท ComfyUI/Jupyter และดู log ย้อนหลัง 400 บรรทัด

---

## 2. ComfyUI พอร์ต 8188 — ใช้งาน Krea 2

### เปิด workflow สำเร็จรูป

ComfyUI v0.26.0 ขึ้นไปมี workflow Krea 2 ให้ในตัว ไม่ต้องลง custom node

> เมนู **Workflow → Browse Templates → Image → Krea 2**

เลือก template แล้วมันจะเช็กให้เองว่าขาดไฟล์ไหน (เราโหลดไว้ให้ครบแล้ว) กด **Run** ได้เลย

### โหนดหลักที่ workflow ใช้

| โหนด | ไฟล์ |
|---|---|
| `UNETLoader` / Load Diffusion Model | `krea2_turbo_fp8_scaled.safetensors` |
| `CLIPLoader` / Load Text Encoder | `qwen3vl_4b_fp8_scaled.safetensors` |
| `VAELoader` | `qwen_image_vae.safetensors` |
| `LoraLoaderModelOnly` (ถ้าใช้) | LoRA ที่โหลดมาเพิ่ม |

### ค่าที่ใช้ได้ผลดี

| | Turbo | RAW |
|---|---|---|
| Steps | **8** (4 = พรีวิวเร็ว) | **52** |
| CFG | **1.0** — สูงกว่านี้ภาพจะแบน/สีเพี้ยน | 3.5–5.0 |
| Sampler | **`euler`** | `euler` |
| Scheduler | **`simple`** | `simple` / `beta` |
| Denoise | 1.0 | 1.0 |
| ความละเอียด | 1024–2048 | 1024–2048 |

ช่อง Turbo คือค่าที่ template `image_krea2_turbo_t2i` ของ ComfyUI ตั้งมาให้จริง
(`KSampler: 8 / cfg 1 / euler / simple / denoise 1`) เริ่มจากค่านี้ก่อนแล้วค่อยปรับ

### ใช้ LoRA ที่โหลดมา

1. โหลด LoRA จาก Dashboard (ปลายทาง `loras`)
2. ใน ComfyUI กด **R** หรือ Refresh เพื่อให้เห็นไฟล์ใหม่ (ไม่ต้องรีสตาร์ท)
3. เพิ่มโหนด **LoraLoaderModelOnly** คั่นระหว่าง `UNETLoader` กับ sampler
4. เริ่มที่ `strength 0.8` แล้วปรับ
5. ถ้ามี trigger word ให้ใส่ในพรอมป์ — Dashboard แสดง trigger word ของ LoRA จาก Civitai ให้ตอนตรวจสอบลิงก์

> LoRA ที่เทรนกับ SDXL/Flux/Pony **ใช้กับ Krea 2 ไม่ได้** ต้องเป็น LoRA ของ Krea 2 เท่านั้น
> บน Civitai กรอง Base Model เป็น Krea 2

#### Trigger word ของ Style LoRA ทางการ (strength แนะนำ `1.0`)

| ไฟล์ | trigger word |
|---|---|
| `krea2_darkbrush` | `monochrome ink wash style` |
| `krea2_dotmatrix` | `monochrome stippling style` |
| `krea2_kidsdrawing` | `naive expressive sketch style` |
| `krea2_neondrip` | `textured abstract style` |
| `krea2_rainywindow` | `rainy window style` |
| `krea2_retroanime` | `purple retro anime style` |
| `krea2_softwatercolor` | `art deco watercolor style` |
| `krea2_sunsetblur` | `ethereal motion blur style` |
| `krea2_vintagetarot` | `vintage tarot style` |

### ลง custom node เพิ่ม

ComfyUI-Manager ติดตั้งมาให้แล้ว — กดปุ่ม **Manager** มุมขวาบน → **Custom Nodes Manager**
ติดตั้งเสร็จให้กด **รีสตาร์ท ComfyUI** ในแท็บระบบของ Dashboard (หรือปุ่ม Restart ของ Manager)

---

## 3. JupyterLab พอร์ต 8888

เปิด `http://IP:พอร์ตที่แมปกับ8888/lab?token=JUPYTER_TOKEN`

- root อยู่ที่ `/workspace` — เห็น `ComfyUI/models`, `ComfyUI/output`, `notebooks/`
- **File → New → Terminal** ได้เชลล์เต็ม (venv `/opt/venv` อยู่ใน PATH แล้ว)
- ดาวน์โหลดผลงาน: คลิกขวาไฟล์ใน `ComfyUI/output` → **Download**

---

## 4. `modelctl` — CLI ใน terminal

ใช้ได้จาก Jupyter terminal หรือ SSH ทำงานผ่าน API เดียวกับหน้าเว็บ งานจึงโผล่ในคิวของ Dashboard ด้วย

```bash
modelctl tokens                       # ดูโทเคนทั้งหมด
modelctl catalog                      # ดูรายการโมเดลทั้งหมด (* = ติดตั้งแล้ว)
modelctl install krea2-turbo --watch  # ติดตั้งชุดพร้อมใช้ + ดู progress สด
modelctl get "https://civitai.com/models/1234?modelVersionId=5678"
modelctl get Comfy-Org/Krea-2:loras/krea2_neondrip.safetensors
modelctl get <url> --folder loras --name my_lora.safetensors
modelctl get <hf-repo> --all          # โหลดทุกไฟล์ใน repo
modelctl jobs --watch                 # ดูคิวแบบ realtime
modelctl list loras                   # ดูไฟล์ในโฟลเดอร์
modelctl key civitai <API_KEY>        # บันทึก + ทดสอบคีย์
```

---

## 5. ปรับแต่งเพิ่ม

### ลง custom node อัตโนมัติทุกครั้งที่บูต

อัปโหลด `scripts/provisioning-example.sh` ขึ้น GitHub Gist (raw URL) แล้วใส่ใน Docker Options

```
-e PROVISIONING_SCRIPT=https://gist.githubusercontent.com/.../provision.sh
```

### เปลี่ยนสิ่งที่โหลดอัตโนมัติตอนบูตแรก

```
-e AUTO_INSTALL=krea2-turbo-nvfp4,krea2-styles,upscalers
-e AUTO_INSTALL=krea2-turbo-mxfp8,krea2-all-loras
-e AUTO_INSTALL=none
```

ทำงานครั้งเดียวต่อ instance (จำสถานะไว้ที่ `/workspace/.config/modelhub/state.json`)
ถ้าอยากให้รันใหม่ ลบไฟล์นั้นแล้วรีสตาร์ท

### VRAM ไม่พอ

```
-e COMFY_ARGS=--reserve-vram 1.5        # RTX 4090
-e COMFY_ARGS=--lowvram                 # การ์ดเล็ก
-e AUTO_INSTALL=krea2-turbo-nvfp4       # RTX 50xx: ใช้ FP4 กินน้อยกว่า
```

---

## 6. แก้ปัญหา

| อาการ | วิธีแก้ |
|---|---|
| ดาวน์โหลด Civitai ขึ้น 401/403 | ยังไม่ได้ใส่ API key หรือคีย์หมดอายุ → แท็บ API Keys แล้วกดทดสอบ |
| HF ขึ้น gated/private | เข้าหน้า repo บนเว็บ กด Accept license ก่อน แล้วใส่ HF token |
| โหลดค้างที่ 0% | เช็ก log ในแท็บระบบ · เครือข่ายเครื่องอาจถูกจำกัด · กดยกเลิกแล้วโหลดใหม่ (resume ต่อได้) |
| ไฟล์ไม่ครบ / ขนาดไม่ตรง | กดโหลดซ้ำ ระบบจะ resume ต่อจากเดิม (aria2 `--continue`) |
| ComfyUI ไม่เห็นโมเดลใหม่ | กด **R** หรือ Refresh ในหน้า ComfyUI · ถ้ายังไม่เห็นให้รีสตาร์ท ComfyUI จากแท็บระบบ |
| `CUDA out of memory` | ลดความละเอียด · ใส่ `--reserve-vram` · เปลี่ยนไปใช้ nvfp4 |
| Dashboard เข้าไม่ได้ | ตรวจว่าใส่ `-p 8189:8189` ใน Docker Options · เอาโทเคนจาก Instance Logs |
| ลืมโทเคน | Jupyter terminal → `cat /workspace/.credentials` หรือ `modelctl tokens` |
