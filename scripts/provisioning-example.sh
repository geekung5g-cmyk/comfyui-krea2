#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ตัวอย่าง PROVISIONING_SCRIPT
#
# วิธีใช้: อัปโหลดไฟล์นี้ขึ้น GitHub Gist / raw URL แล้วใส่ใน Docker Options
#   -e PROVISIONING_SCRIPT=https://gist.githubusercontent.com/.../provision.sh
#
# สคริปต์นี้รันเป็น root ในเบื้องหลังตอนบูต ไม่บล็อกการเปิด ComfyUI
# log อยู่ที่ /var/log/services/provisioning.log (ดูได้ในแท็บระบบของ Dashboard)
# ---------------------------------------------------------------------------
set -Eeuo pipefail

export PATH="/opt/venv/bin:${PATH}"
COMFY_NODES="/workspace/ComfyUI/custom_nodes"
mkdir -p "${COMFY_NODES}"

echo "[provision] started at $(date)"

# --- custom nodes ที่อยากได้ทุกครั้ง -------------------------------------
NODES=(
  "https://github.com/rgthree/rgthree-comfy"
  "https://github.com/kijai/ComfyUI-KJNodes"
  "https://github.com/cubiq/ComfyUI_essentials"
  "https://github.com/ltdrdata/ComfyUI-Impact-Pack"
  "https://github.com/WASasquatch/was-node-suite-comfyui"
)

for repo in "${NODES[@]}"; do
  name="$(basename "${repo}")"
  dest="${COMFY_NODES}/${name}"
  if [[ -d "${dest}" ]]; then
    echo "[provision] ${name} มีอยู่แล้ว ข้าม"
    continue
  fi
  echo "[provision] clone ${name}"
  if git clone --depth 1 "${repo}" "${dest}"; then
    [[ -f "${dest}/requirements.txt" ]] && pip install -r "${dest}/requirements.txt" || true
  else
    echo "[provision] clone ${name} ไม่สำเร็จ ข้ามไป"
  fi
done

# --- โมเดลเพิ่มเติมผ่าน modelctl -----------------------------------------
# ใช้ catalog id หรือลิงก์ตรงก็ได้ งานจะไปโผล่ในคิวของ Dashboard
#
# modelctl install upscalers krea2-styles
# modelctl get "https://civitai.com/models/1234?modelVersionId=5678" --folder loras
# modelctl get "Comfy-Org/Krea-2:loras/krea2_retroanime.safetensors"

# --- pip เพิ่มเติม --------------------------------------------------------
# pip install --no-cache-dir insightface onnxruntime-gpu

# --- รีสตาร์ท ComfyUI ให้เห็น node ใหม่ ----------------------------------
echo "[provision] restarting ComfyUI"
supervisorctl -c /etc/supervisor/supervisord.conf restart comfyui || true

echo "[provision] finished at $(date)"
