-- ai_hook.lua — DESACTIVADO (solo botón desde el viewer dispara la IA)
-- Mantiene logs básicos y NO llama al backend automáticamente.
-- Si quieres reactivar el auto-análisis, cambia ENABLE_AUTO a true.

local ENABLE_AUTO = false  -- << NO tocar: queremos que SOLO el botón del viewer dispare la IA

local function log_info(msg)
  if type(PrintInfo) == "function" then PrintInfo(msg) end
end
local function log_warn(msg)
  if type(PrintWarning) == "function" then PrintWarning(msg) end
end
local function log_error(msg)
  if type(PrintError) == "function" then PrintError(msg) end
end

function OnOrthancStarted()
  log_info("ai_hook.lua cargado (modo DESACTIVADO: análisis sólo por botón del viewer)")
end

function OnStoredInstance(instanceId, tags, metadata, origin)
  -- Dejamos trazas útiles, pero NO analizamos al subir
  local mod = tags["Modality"] or "UNK"
  local study_uid = tags["StudyInstanceUID"] or "UNK"
  log_info(string.format("AI Hook: instancia recibida (Mod=%s, StudyUID=%s) [AUTO=%s]",
    tostring(mod), tostring(study_uid), tostring(ENABLE_AUTO)))

  if not ENABLE_AUTO then
    -- Nada más que hacer: el análisis lo dispara el botón del viewer (backend /analyze)
    return
  end

  -- (Si algún día reactivas el auto-análisis, descomenta esto)
  -- if tags["Modality"] ~= "CT" then return end
  -- if not study_uid or study_uid == "" then return end
  -- local url = "http://127.0.0.1:8001/analyze"
  -- local body = '{"orthanc":"http://127.0.0.1:8042","StudyInstanceUID":"' .. study_uid .. '","replace_existing":true}'
  -- local headers = { ["Content-Type"] = "application/json" }
  -- local ok, resp = pcall(function() return HttpPost(url, body, headers) end)
  -- if not ok then log_warn("AI Hook: fallo al llamar backend: " .. tostring(resp)) end
end
