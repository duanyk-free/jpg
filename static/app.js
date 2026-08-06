/* === Online Image Tool — Frontend App === */
(function () {
  "use strict";

  // --- State ---
  const state = {
    uploadId: null,
    fileName: null,
    originalInfo: null,
    resultId: null,
    resultInfo: null,
    activeTab: "resize",
    // Resize state
    resizeWidth: null,
    resizeHeight: null,
    resizeKeepAspect: true,
    resizePercentage: 100,
    // Convert state
    convertFormat: "JPEG",
    convertQuality: 90,
    // ID photo state
    idPhotoSize: "1inch",
    idPhotoBgColor: "white",
    // Presets from server
    resizePresets: {},
    idPhotoPresets: {},
    formats: {},
  };

  // --- DOM refs ---
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => document.querySelectorAll(s);

  const dom = {
    dropZone: $("#drop-zone"),
    fileInput: $("#file-input"),
    previewArea: $("#preview-area"),
    imgOriginal: $("#img-original"),
    imgResult: $("#img-result"),
    originalInfo: $("#original-info"),
    resultInfo: $("#result-info"),
    resultActions: $("#result-actions"),
    btnDownload: $("#btn-download"),
    previewFilename: $("#preview-filename"),
    previewDimensions: $("#preview-dimensions"),
    previewSize: $("#preview-size"),
    statusText: $("#status-text"),
    fileNameDisplay: $("#file-name-display"),
    // Resize
    resizePreset: $("#resize-preset"),
    resizeWidth: $("#resize-width"),
    resizeHeight: $("#resize-height"),
    resizeKeepAspect: $("#resize-keep-aspect"),
    resizePercentage: $("#resize-percentage"),
    resizePercentageLabel: $("#resize-percentage-label"),
    btnResize: $("#btn-resize"),
    // Convert
    formatOptions: $("#format-options"),
    convertQuality: $("#convert-quality"),
    convertQualityLabel: $("#convert-quality-label"),
    qualityGroup: $("#quality-group"),
    btnConvert: $("#btn-convert"),
    // White BG
    btnWhiteBg: $("#btn-white-bg"),
    // ID Photo
    idPhotoSize: $("#id-photo-size"),
    idPhotoPanel: $("#id-photo-panel"),
    btnIdPhoto: $("#btn-id-photo"),
    // Models
    whiteBgModel: $("#white-bg-model"),
    idPhotoModel: $("#id-photo-model"),
  };

  // --- Helpers ---
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  function showToast(msg, type) {
    type = type || "";
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3000);
  }

  function setStatus(msg) {
    dom.statusText.textContent = msg;
  }

  function setProcessing(btn, active) {
    if (active) {
      btn.disabled = true;
      btn.dataset.origText = btn.textContent;
      btn.textContent = "⏳ 处理中...";
    } else {
      btn.disabled = false;
      btn.textContent = btn.dataset.origText || btn.textContent;
    }
  }

  // --- API ---
  async function api(url, opts) {
    if (opts === undefined) opts = {};
    try {
      const res = await fetch(url, opts);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "HTTP " + res.status);
      }
      const ct = res.headers.get("content-type") || "";
      if (ct.includes("image/")) {
        const blob = await res.blob();
        return { _blob: blob, _mime: ct.split(";")[0] };
      }
      return res.json();
    } catch (e) {
      if (e.name === "AbortError") throw e;
      console.error("API error:", e);
      showToast(e.message, "error");
      throw e;
    }
  }

  // --- Upload ---
  async function uploadFile(file) {
    setStatus("正在上传 " + file.name + "...");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const data = await api("/api/upload", { method: "POST", body: formData });
      state.uploadId = data.id;
      state.fileName = data.name;
      state.originalInfo = data.info;
      state.resultId = null;
      state.resultInfo = null;

      // Load preview
      dom.imgOriginal.src = "/api/preview/" + state.uploadId + "?t=" + Date.now();
      dom.imgResult.src = "";
      dom.resultActions.style.display = "none";

      // Update UI
      dom.dropZone.style.display = "none";
      dom.previewArea.style.display = "flex";
      dom.fileNameDisplay.textContent = data.name;
      dom.previewFilename.textContent = data.name;
      dom.previewDimensions.textContent = data.info.width + " × " + data.info.height;
      dom.previewSize.textContent = formatBytes(data.info.file_size);
      dom.originalInfo.textContent = data.info.format + " · " + data.info.mode + " · " + data.info.width + "×" + data.info.height;

      // Populate resize inputs
      dom.resizeWidth.value = data.info.width;
      dom.resizeHeight.value = data.info.height;
      state.resizeWidth = data.info.width;
      state.resizeHeight = data.info.height;

      setStatus("已加载: " + data.name + " (" + data.info.width + "×" + data.info.height + ")");
    } catch (e) {
      setStatus("上传失败: " + e.message);
    }
  }

  // --- Operations ---
  let abortController = null;

  async function doResize() {
    if (!state.uploadId) { showToast("请先上传图片", "error"); return; }

    const body = { upload_id: state.uploadId };
    const pct = parseInt(dom.resizePercentage.value);

    if (pct !== 100) {
      body.percentage = pct;
    } else {
      const w = parseInt(dom.resizeWidth.value);
      const h = parseInt(dom.resizeHeight.value);
      if (w && w > 0) body.width = w;
      if (h && h > 0) body.height = h;
      body.keep_aspect = dom.resizeKeepAspect.checked;
    }

    // Cancel previous in-flight request
    if (abortController) abortController.abort();
    abortController = new AbortController();

    setProcessing(dom.btnResize, true);
    setStatus("正在调整尺寸...");
    try {
      const data = await api("/api/resize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortController.signal,
        body: JSON.stringify(body),
      });

      state.resultId = data.result_id;
      state.resultInfo = data;
      dom.imgResult.src = "/api/result/" + data.result_id + "?t=" + Date.now();
      dom.resultInfo.textContent = data.width + "×" + data.height + " · " + formatBytes(data.size);
      dom.resultActions.style.display = "block";
      setStatus("尺寸调整完成: " + data.width + "×" + data.height + " (" + formatBytes(data.size) + ")");
      showToast("尺寸调整完成", "success");
    } catch (e) {
      if (e.name !== "AbortError") {
        setStatus("处理失败: " + e.message);
      }
    } finally {
      setProcessing(dom.btnResize, false);
    }
  }

  async function doConvert() {
    if (!state.uploadId) { showToast("请先上传图片", "error"); return; }

    const body = {
      upload_id: state.uploadId,
      format: state.convertFormat,
      quality: parseInt(dom.convertQuality.value),
    };

    setStatus("正在转换格式...");
    try {
      const data = await api("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      state.resultId = data.result_id;
      state.resultInfo = data;
      dom.imgResult.src = "/api/result/" + data.result_id + "?t=" + Date.now();
      dom.resultInfo.textContent = data.format + " · " + data.width + "×" + data.height + " · " + formatBytes(data.size);
      dom.resultActions.style.display = "block";
      setStatus("格式转换完成: " + data.format + " (" + formatBytes(data.size) + ")");
      showToast("格式转换完成", "success");
    } catch (e) {
      setStatus("转换失败: " + e.message);
    }
  }

  async function doWhiteBg() {
    if (!state.uploadId) { showToast("请先上传图片", "error"); return; }

    setProcessing(dom.btnWhiteBg, true);
    setStatus("正在 AI 抠图 + 生成白底照片...");
    try {
      const data = await api("/api/white-bg", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          upload_id: state.uploadId,
          model: dom.whiteBgModel.value,
        }),
      });

      state.resultId = data.result_id;
      state.resultInfo = data;
      dom.imgResult.src = "/api/result/" + data.result_id + "?t=" + Date.now();
      dom.resultInfo.textContent = data.width + "×" + data.height + " · " + formatBytes(data.size);
      dom.resultActions.style.display = "block";
      setStatus("白底照片生成完成 (" + formatBytes(data.size) + ")");
      showToast("白底照片生成完成", "success");
    } catch (e) {
      setStatus("处理失败: " + e.message);
    } finally {
      setProcessing(dom.btnWhiteBg, false);
    }
  }

  async function doIdPhoto() {
    if (!state.uploadId) { showToast("请先上传图片", "error"); return; }

    setProcessing(dom.btnIdPhoto, true);
    const body = {
      upload_id: state.uploadId,
      size: state.idPhotoSize,
      bg_color: state.idPhotoBgColor,
      model: dom.idPhotoModel.value,
    };

    setStatus("正在 AI 抠图 + 生成证件照...");
    try {
      const data = await api("/api/id-photo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      state.resultId = data.result_id;
      state.resultInfo = data;
      dom.imgResult.src = "/api/result/" + data.result_id + "?t=" + Date.now();
      dom.resultInfo.textContent = data.label + " · " + data.width + "×" + data.height + " · " + formatBytes(data.size);
      dom.resultActions.style.display = "block";
      setStatus("证件照生成完成: " + data.label + " (" + formatBytes(data.size) + ")");
      showToast("证件照生成完成", "success");
    } catch (e) {
      setStatus("处理失败: " + e.message);
    } finally {
      setProcessing(dom.btnIdPhoto, false);
    }
  }

  function downloadResult() {
    if (!state.resultId) return;
    const a = document.createElement("a");
    a.href = "/api/download/" + state.resultId;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // --- Load presets ---
  async function loadPresets() {
    try {
      const [resizeData, idPhotoData, formatsData, modelsData] = await Promise.all([
        api("/api/presets/resize"),
        api("/api/presets/id-photo"),
        api("/api/presets/formats"),
        api("/api/presets/models"),
      ]);
      state.resizePresets = resizeData;
      state.idPhotoPresets = idPhotoData;
      state.formats = formatsData;
      state.models = modelsData.models;
      state.defaultModel = modelsData.default;

      // Populate resize preset dropdown
      dom.resizePreset.innerHTML = '<option value="">自定义...</option>';
      Object.entries(resizeData).forEach(([key, val]) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.label + " (" + val.width + "×" + val.height + ")";
        dom.resizePreset.appendChild(opt);
      });

      // Populate ID photo size dropdown
      dom.idPhotoSize.innerHTML = "";
      Object.entries(idPhotoData).forEach(([key, val]) => {
        const opt = document.createElement("option");
        opt.value = key;
        opt.textContent = val.label + " (" + val.width + "×" + val.height + "px)";
        dom.idPhotoSize.appendChild(opt);
      });

      // Populate model selectors (white-bg and id-photo)
      [dom.whiteBgModel, dom.idPhotoModel].forEach(sel => {
        sel.innerHTML = "";
        Object.entries(state.models).forEach(([key, label]) => {
          const opt = document.createElement("option");
          opt.value = key;
          opt.textContent = label;
          if (key === state.defaultModel) opt.selected = true;
          sel.appendChild(opt);
        });
      });
    } catch (e) {
      console.error("Failed to load presets:", e);
    }
  }

  // --- Event bindings ---

  // File selection
  dom.fileInput.addEventListener("change", () => {
    const file = dom.fileInput.files[0];
    if (file) uploadFile(file);
    dom.fileInput.value = "";
  });

  $("#btn-select-file").addEventListener("click", () => dom.fileInput.click());
  $("#btn-new-file").addEventListener("click", () => dom.fileInput.click());

  // Drag and drop
  dom.dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dom.dropZone.classList.add("drag-over");
  });
  dom.dropZone.addEventListener("dragleave", () => {
    dom.dropZone.classList.remove("drag-over");
  });
  dom.dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dom.dropZone.classList.remove("drag-over");
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });

  // Global drag and drop (anywhere in the window)
  document.addEventListener("dragover", (e) => { e.preventDefault(); });
  document.addEventListener("drop", (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("image/")) {
      uploadFile(file);
    }
  });

  // Sidebar tabs
  $$(".sidebar-tab").forEach(btn => {
    btn.addEventListener("click", () => {
      state.activeTab = btn.dataset.tab;
      $$(".sidebar-tab").forEach(b => b.classList.toggle("active", b === btn));
      $$(".sidebar-panel").forEach(p => p.classList.toggle("active", p.id === "panel-" + btn.dataset.tab));
    });
  });

  // Resize controls
  dom.resizePreset.addEventListener("change", () => {
    const key = dom.resizePreset.value;
    if (key && state.resizePresets[key]) {
      const preset = state.resizePresets[key];
      dom.resizeWidth.value = preset.width;
      dom.resizeHeight.value = preset.height;
      state.resizeWidth = preset.width;
      state.resizeHeight = preset.height;
      dom.resizePercentage.value = 100;
      dom.resizePercentageLabel.textContent = "100%";
      // Preset and keep-aspect are mutually exclusive
      dom.resizeKeepAspect.checked = false;
      state.resizeKeepAspect = false;
      dom.resizeKeepAspect.disabled = true;
    } else {
      dom.resizeKeepAspect.disabled = false;
    }
  });

  dom.resizeWidth.addEventListener("input", () => {
    dom.resizePreset.value = "";
    dom.resizeKeepAspect.disabled = false;
    state.resizeWidth = parseInt(dom.resizeWidth.value) || null;
    // Auto-fill height when keep-aspect is checked
    if (dom.resizeKeepAspect.checked && state.originalInfo && state.resizeWidth) {
      const ratio = state.originalInfo.height / state.originalInfo.width;
      const h = Math.round(state.resizeWidth * ratio);
      dom.resizeHeight.value = h;
      state.resizeHeight = h;
    }
  });
  dom.resizeHeight.addEventListener("input", () => {
    dom.resizePreset.value = "";
    dom.resizeKeepAspect.disabled = false;
    state.resizeHeight = parseInt(dom.resizeHeight.value) || null;
    // Auto-fill width when keep-aspect is checked
    if (dom.resizeKeepAspect.checked && state.originalInfo && state.resizeHeight) {
      const ratio = state.originalInfo.width / state.originalInfo.height;
      const w = Math.round(state.resizeHeight * ratio);
      dom.resizeWidth.value = w;
      state.resizeWidth = w;
    }
  });
  dom.resizeKeepAspect.addEventListener("change", () => {
    state.resizeKeepAspect = dom.resizeKeepAspect.checked;
    if (state.resizeKeepAspect) {
      dom.resizePreset.value = "";
    }
  });
  dom.resizePercentage.addEventListener("input", () => {
    dom.resizePercentageLabel.textContent = dom.resizePercentage.value + "%";
    if (dom.resizePercentage.value !== "100") {
      dom.resizePreset.value = "";
      dom.resizeKeepAspect.disabled = false;
    }
  });
  dom.btnResize.addEventListener("click", doResize);

  // Convert controls
  dom.formatOptions.querySelectorAll(".format-option").forEach(opt => {
    opt.addEventListener("click", () => {
      dom.formatOptions.querySelectorAll(".format-option").forEach(o => o.classList.remove("selected"));
      opt.classList.add("selected");
      state.convertFormat = opt.dataset.format;
      // Show/hide quality slider for lossless formats
      const isLossless = opt.dataset.format === "PNG" || opt.dataset.format === "BMP";
      dom.qualityGroup.style.display = isLossless ? "none" : "";
    });
  });
  dom.convertQuality.addEventListener("input", () => {
    dom.convertQualityLabel.textContent = dom.convertQuality.value + "%";
    state.convertQuality = parseInt(dom.convertQuality.value);
  });
  dom.btnConvert.addEventListener("click", doConvert);

  // White BG
  dom.btnWhiteBg.addEventListener("click", doWhiteBg);

  // ID Photo controls
  dom.idPhotoSize.addEventListener("change", () => {
    state.idPhotoSize = dom.idPhotoSize.value;
  });

  // BG color options
  $$(".bg-color-option").forEach(opt => {
    opt.addEventListener("click", () => {
      $$(".bg-color-option").forEach(o => o.classList.remove("selected"));
      opt.classList.add("selected");
      state.idPhotoBgColor = opt.dataset.color;
    });
  });

  dom.btnIdPhoto.addEventListener("click", doIdPhoto);

  // ID photo panel toggle
  $("#id-photo-header").addEventListener("click", () => {
    dom.idPhotoPanel.classList.toggle("collapsed");
  });

  // Download button
  dom.btnDownload.addEventListener("click", downloadResult);

  // Keyboard shortcut: Ctrl+S to download
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s") {
      e.preventDefault();
      if (state.resultId) downloadResult();
    }
  });

  // --- Init ---
  loadPresets();
  setStatus("就绪 — 请上传图片开始使用");
})();
