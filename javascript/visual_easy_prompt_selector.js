(function () {
  "use strict";

  const state = {
    path: "",
    tag: "",
    image: "all",
    query: "",
    searchMode: "and",
  };

  function q(selector, root = document) {
    return root.querySelector(selector);
  }

  function qa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }
  function protectToolbarControls(toolbar, selector) {
    for (const control of qa(selector, toolbar)) {
      for (const eventName of ["pointerdown", "mousedown", "click", "keydown"]) {
        control.addEventListener(eventName, (event) => {
          event.stopPropagation();
        });
      }
    }
  }

  let lazyImageObserver = null;

  function loadCardImage(card) {
    const image = q("img.preview[data-veps-src]", card);
    if (!image || image.dataset.vepsLoaded === "1") return;
    image.src = image.dataset.vepsSrc;
    image.dataset.vepsLoaded = "1";
  }

  function ensureLazyImageObserver() {
    if (lazyImageObserver || !("IntersectionObserver" in window)) return lazyImageObserver;
    lazyImageObserver = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const image = entry.target;
        const card = image.closest(".veps-extra-card") || image;
        loadCardImage(card);
        lazyImageObserver.unobserve(image);
      }
    }, { rootMargin: "360px 0px" });
    return lazyImageObserver;
  }

  function setupLazyImages(root = document) {
    const observer = ensureLazyImageObserver();
    for (const image of qa("img.preview[data-veps-src]", root)) {
      if (image.dataset.vepsLoaded === "1" || image.dataset.vepsObserved === "1") continue;
      image.dataset.vepsObserved = "1";
      if (observer) {
        observer.observe(image);
      } else {
        const card = image.closest(".veps-extra-card");
        if (!card || !card.classList.contains("veps-filter-hidden")) loadCardImage(card || image);
      }
    }
  }
  function pageForCard(card) {
    return card.closest(".extra-page") || card.closest("[id$='_visual_eps']");
  }

  function visualEpsPages() {
    return qa("[id$='_visual_eps']");
  }

  // The page id is "<tabname>_visual_eps" (tabname: txt2img / img2img).
  // Forge moves #<tabname>_prompt into the page only with the Compact prompt layout, so look it up by id.
  function positivePromptTextarea(page) {
    const tabname = page && page.id ? page.id.replace(/_visual_eps$/, "") : "";
    return tabname ? q(`#${tabname}_prompt textarea`) : null;
  }

  function clearPositivePrompt(page) {
    const textarea = positivePromptTextarea(page);
    if (!textarea) return;
    textarea.value = "";
    // Tell Gradio about the change; Forge's updateInput() does this, with a plain input event as a fallback.
    if (typeof updateInput === "function") {
      updateInput(textarea);
    } else {
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
    }
  }

  function cardTitle(card) {
    const title = q(".name", card);
    return title ? title.textContent.trim() : card.dataset.name || "Visual EPS";
  }

  function cardDescription(card) {
    const desc = q(".description", card);
    return desc ? desc.textContent.trim() : "";
  }

  function cardImage(card) {
    const image = q("img.preview", card);
    return image ? image.dataset.vepsSrc || image.src : "";
  }

  function uniqueSorted(values) {
    return Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b));
  }

  function escapeHtml(value) {
    return String(value || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function parseTokens(query) {
    const tokens = [];
    const re = /"([^"]+)"|(\S+)/g;
    let match;
    while ((match = re.exec(query || ""))) {
      tokens.push(String(match[1] || match[2] || "").toLowerCase().replace(/^#/, ""));
    }
    return tokens.filter(Boolean);
  }

  function cardSearchBlob(card) {
    return [
      card.textContent || "",
      card.dataset.vepsCategory || "",
      card.dataset.vepsSource || "",
      card.dataset.vepsTags || "",
    ]
      .join(" ")
      .toLowerCase();
  }

  function pageCards(page) {
    return qa(".veps-extra-card", page);
  }

  function isTreeLeaf(card) {
    return card.matches("li.tree-list-item");
  }

  // Same "source/category" path the source tree and the dirs view use.
  function cardPath(card) {
    return `${card.dataset.vepsSource || "unknown.yml"}/${card.dataset.vepsCategory || "Root"}`;
  }

  function pathMatches(card) {
    if (!state.path) return true;
    const path = cardPath(card);
    return path === state.path || path.startsWith(`${state.path}/`);
  }

  function setPathFilter(path) {
    state.path = path || "";
    applyFilters();
  }

  function clearNativeExtraSearch(page) {
    const nativeSearch = nativeExtraSearchForPage(page);
    if (!nativeSearch || !nativeSearch.value) return;
    nativeSearch.value = "";
    nativeSearch.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function loadedPromptCount(page) {
    return qa(".card.veps-extra-card", page).length;
  }


  function nativeExtraSearchForPage(page) {
    return page && page.id ? document.getElementById(`${page.id}_extra_search`) : null;
  }

  function updateLoadControls(page, { loaded = false, loading = false, message = "" } = {}) {
    const button = q(".veps-load-button", page);
    const status = q(".veps-load-status", page);
    if (button) {
      button.disabled = loading;
      button.textContent = loading ? "Loading Visual EPS..." : loaded ? "Reload Visual EPS" : "Load Visual EPS";
    }
    if (status) status.textContent = message;
  }

  function syncToolbarTags(page) {
    const tagList = q(".veps-tag-list", page);
    if (!tagList) return;
    const tags = uniqueSorted(
      pageCards(page).flatMap((card) =>
        (card.dataset.vepsTags || "")
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean)
      )
    );
    tagList.innerHTML = "";
    for (const tag of tags) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = `#${tag}`;
      button.dataset.tag = tag;
      tagList.appendChild(button);
    }
  }

  async function getLoadStatus() {
    const response = await fetch("/visual-eps/status");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Failed to read Visual EPS status");
    return data;
  }

  function waitForVisualEpsRefresh(page, expectedRevision) {
    let attempts = 0;
    const poll = () => {
      const tree = q(".veps-source-tree", page);
      const refreshComplete = tree && tree.dataset.vepsRevision === String(expectedRevision);
      if (refreshComplete) {
        page.dataset.vepsLoading = "0";
        syncToolbarTags(page);
        bindCards();
        updateLoadControls(page, {
          loaded: true,
          message: `${loadedPromptCount(page)} prompts loaded`,
        });
        return;
      }
      attempts += 1;
      if (attempts >= 600) {
        page.dataset.vepsLoading = "0";
        updateLoadControls(page, { loaded: false, message: "Load timed out. Try Load Visual EPS again." });
        return;
      }
      window.setTimeout(poll, 500);
    };
    window.setTimeout(poll, 500);
  }

  async function requestVisualEpsLoad(page, force = false) {
    if (!page || page.dataset.vepsLoading === "1") return;
    page.dataset.vepsLoading = "1";
    updateLoadControls(page, { loading: true, message: "Reading EPS data after WebUI startup..." });
    try {
      const response = await fetch("/visual-eps/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ force }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Failed to start Visual EPS load");
      const refreshButton = document.getElementById(`${page.id}_extra_refresh_internal`);
      if (!refreshButton) throw new Error("Visual EPS refresh control is unavailable");
      refreshButton.click();
      waitForVisualEpsRefresh(page, data.revision);
    } catch (error) {
      page.dataset.vepsLoading = "0";
      updateLoadControls(page, { loaded: false, message: error.message || String(error) });
    }
  }

  async function maybeLoadVisualEpsOnOpen(page) {
    if (!page || pageCards(page).length || page.dataset.vepsLoading === "1") return;
    try {
      const status = await getLoadStatus();
      updateLoadControls(page, { loaded: status.loaded, message: status.loaded ? "Ready to display" : "Not loaded" });
      if (status.load_mode === "on_tab_open") await requestVisualEpsLoad(page, false);
    } catch (error) {
      updateLoadControls(page, { loaded: false, message: error.message || String(error) });
    }
  }
  // Source buttons (dirs view) and tree folders filter by path in Visual EPS itself,
  // instead of going through Forge's native search box, so they combine with the toolbar filters.
  function visualEpsTreeClickGuard(event) {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;

    const sourceButton = target.closest(".veps-source-button");
    if (sourceButton) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const path = sourceButton.dataset.vepsPath || "";
      setPathFilter(state.path === path ? "" : path);
      return;
    }

    const content = target.closest(".veps-source-tree .tree-list-content-dir");
    if (!content) return;
    const page = content.closest("[id$='_visual_eps']");
    if (!page) return;
    const clickedChevron = target.closest(".tree-list-item-action--leading, .tree-list-item-action-chevron");
    if (clickedChevron) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const subgroup = content.nextElementSibling && content.nextElementSibling.matches("ul") ? content.nextElementSibling : null;
    const expanded = subgroup && !subgroup.hasAttribute("hidden");
    const selected = "selected" in content.dataset;

    for (const other of qa(".veps-source-tree .tree-list-content[data-selected]", page)) {
      delete other.dataset.selected;
    }
    if (selected && (expanded || !subgroup)) {
      if (subgroup) {
        subgroup.setAttribute("hidden", "");
        delete content.dataset.expanded;
      }
      setPathFilter("");
      return;
    }
    if (subgroup) {
      subgroup.removeAttribute("hidden");
      content.dataset.expanded = "";
    }
    content.dataset.selected = "";
    setPathFilter(content.dataset.path || "");
  }

  function buildToolbar(page) {
    if (page.dataset.vepsToolbarBound === "1") {
      syncToolbarTags(page);
      return;
    }
    page.dataset.vepsToolbarBound = "1";

    const toolbar = document.createElement("div");
    toolbar.className = "veps-extra-toolbar";
    toolbar.innerHTML = `
      <div class="veps-load-row">
        <button type="button" class="veps-clear-prompt" title="Clear the positive prompt of this tab">Clear prompt</button>
        <span class="veps-load-status">Checking load mode...</span>
        <button type="button" class="veps-load-button">Load Visual EPS</button>
      </div>
      <div class="veps-filter-row">
        <input class="veps-local-search" type="search" placeholder="Visual EPS search">
        <select class="veps-search-mode" title="Search mode">
          <option value="and">AND</option>
          <option value="or">OR</option>
        </select>

        <select class="veps-image-select" title="Image filter">
          <option value="all">All images</option>
          <option value="with">Image only</option>
          <option value="without">No image</option>
        </select>
        <button type="button" class="veps-clear-filter">Clear</button>
      </div>
      <div class="veps-active-filter"></div>
      <div class="veps-tag-list"></div>
    `;



    protectToolbarControls(toolbar, ".veps-local-search, .veps-search-mode, .veps-image-select");

    toolbar.addEventListener("click", (event) => {
      if (event.target.closest(".veps-load-button")) {
        event.preventDefault();
        requestVisualEpsLoad(page, true);
        return;
      }
      if (event.target.closest(".veps-clear-prompt")) {
        event.preventDefault();
        clearPositivePrompt(page);
        return;
      }
      const tagButton = event.target.closest("[data-tag]");

      if (tagButton) {
        state.tag = tagButton.dataset.tag || "";
        applyFilters();
      }
      if (event.target.closest(".veps-clear-filter")) {
        state.path = "";
        state.tag = "";
        state.image = "all";
        state.query = "";
        state.searchMode = "and";
        const imageSelect = q(".veps-image-select", toolbar);
        if (imageSelect) imageSelect.value = "all";
        const search = q(".veps-local-search", toolbar);
        if (search) search.value = "";
        const searchMode = q(".veps-search-mode", toolbar);
        if (searchMode) searchMode.value = "and";
        for (const selected of qa(".veps-source-tree .tree-list-content[data-selected]", page)) {
          delete selected.dataset.selected;
        }
        clearNativeExtraSearch(page);
        applyFilters();
      }
    });

    const search = q(".veps-local-search", toolbar);
    search.addEventListener("input", () => {
      state.query = search.value;
      applyFilters();
    });

    const searchMode = q(".veps-search-mode", toolbar);
    searchMode.addEventListener("change", () => {
      state.searchMode = searchMode.value;
      applyFilters();
    });

    const imageSelect = q(".veps-image-select", toolbar);
    imageSelect.addEventListener("change", () => {
      state.image = imageSelect.value;
      applyFilters();
    });

    page.prepend(toolbar);
    clearNativeExtraSearch(page);
    syncToolbarTags(page);
    getLoadStatus()
      .then((status) => {
        if (page.dataset.vepsLoading === "1") return;
        updateLoadControls(page, {
          loaded: status.loaded || pageCards(page).length > 0,
          message: pageCards(page).length > 0 ? `${loadedPromptCount(page)} prompts loaded` : status.loaded ? "Ready to display" : "Not loaded",
        });
      })
      .catch((error) => updateLoadControls(page, { loaded: false, message: error.message || String(error) }));
    applyFilters();
  }

  // While a keyword/tag/image filter is active, hide tree folders without matches
  // and expand the folders that contain matches.
  function syncSourceTree(page, contentFilterActive) {
    const leaves = qa(".veps-source-tree li.veps-extra-card", page);
    if (leaves.length === 0) return;
    const dirs = qa(".veps-source-tree li[data-tree-entry-type='dir']", page);
    if (!contentFilterActive) {
      for (const dir of dirs) dir.classList.remove("veps-filter-hidden");
      return;
    }
    for (const dir of dirs) {
      const hasMatch = q("li.veps-extra-card:not(.veps-filter-hidden)", dir) !== null;
      dir.classList.toggle("veps-filter-hidden", !hasMatch);
      const subgroup = q(":scope > ul.tree-list--subgroup", dir);
      if (hasMatch && subgroup && subgroup.hasAttribute("hidden")) {
        subgroup.removeAttribute("hidden");
        const button = subgroup.previousElementSibling;
        if (button) button.dataset.expanded = "";
      }
    }
  }

  function applyFilters() {
    const tokens = parseTokens(state.query);
    const contentFilterActive = tokens.length > 0 || Boolean(state.tag) || state.image !== "all";
    for (const page of visualEpsPages()) {
      let visible = 0;
      let total = 0;
      let leafVisible = 0;
      let leafTotal = 0;
      const cards = pageCards(page);
      for (const card of cards) {
        const treeLeaf = isTreeLeaf(card);
        const tags = (card.dataset.vepsTags || "").split(",").map((tag) => tag.trim());
        const hasImage = card.dataset.vepsHasImage === "1";
        const blob = cardSearchBlob(card);
        const tagMatch = !state.tag || tags.includes(state.tag);
        const imageMatch =
          state.image === "all" ||
          (state.image === "with" && hasImage) ||
          (state.image === "without" && !hasImage);
        const searchMatch =
          tokens.length === 0 ||
          (state.searchMode === "or"
            ? tokens.some((token) => blob.includes(token))
            : tokens.every((token) => blob.includes(token)));
        // The tree is the navigation itself, so the path filter only narrows the card grid.
        const show = tagMatch && imageMatch && searchMatch && (treeLeaf || pathMatches(card));
        card.classList.toggle("veps-filter-hidden", !show);
        if (treeLeaf) {
          leafTotal += 1;
          if (show) leafVisible += 1;
          continue;
        }
        total += 1;
        if (show) visible += 1;
      }
      syncSourceTree(page, contentFilterActive);
      if (total === 0) {
        // Tree-only layout: report the tree leaves instead.
        visible = leafVisible;
        total = leafTotal;
      }
      const active = q(".veps-active-filter", page);
      if (active) {
        const labels = [];
        if (state.path) labels.push(`Path: ${state.path}`);
        if (state.tag) labels.push(`#${state.tag}`);
        if (state.image !== "all") labels.push(state.image === "with" ? "Image only" : "No image");
        if (state.query) labels.push(`${state.searchMode.toUpperCase()}: ${state.query}`);
        active.textContent = `${visible} / ${total} visible${labels.length ? " - " + labels.join(" / ") : ""}`;
      }
      setupLazyImages(page);
    }
  }

  function ensureModal() {
    let modal = q("#veps-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "veps-modal";
    modal.hidden = true;
    modal.innerHTML = `
      <div class="veps-modal-backdrop"></div>
      <div class="veps-modal-panel">
        <div class="veps-modal-head">
          <strong class="veps-modal-title">Visual EPS</strong>
          <button type="button" class="veps-modal-close">Close</button>
        </div>
        <div class="veps-modal-body"></div>
      </div>
    `;
    modal.addEventListener("click", (event) => {
      if (event.target.closest(".veps-modal-close") || event.target.classList.contains("veps-modal-backdrop")) {
        closeModal();
      }
    });
    document.body.appendChild(modal);
    return modal;
  }

  function openModal(title, body) {
    const modal = ensureModal();
    q(".veps-modal-title", modal).textContent = title;
    const modalBody = q(".veps-modal-body", modal);
    modalBody.innerHTML = "";
    modalBody.appendChild(body);
    modal.hidden = false;
  }

  function closeModal() {
    const modal = q("#veps-modal");
    if (modal) modal.hidden = true;
  }

  async function getItem(id) {
    const response = await fetch(`/visual-eps/item?id=${encodeURIComponent(id)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Failed to load item");
    return data;
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      if (!file) {
        resolve("");
        return;
      }
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(reader.error || new Error("Failed to read file"));
      reader.readAsDataURL(file);
    });
  }


  async function resizeImageFileAsDataUrl(file, maxSize, quality = 0.84) {
    if (!file) return { dataUrl: "", name: "" };
    if (!file.type || !file.type.startsWith("image/")) {
      return { dataUrl: await readFileAsDataUrl(file), name: file.name || "preview" };
    }

    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, maxSize / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    context.drawImage(bitmap, 0, 0, width, height);
    if (bitmap.close) bitmap.close();

    const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/webp", quality));
    if (!blob) return { dataUrl: await readFileAsDataUrl(file), name: file.name || "preview" };
    const dataUrl = await readFileAsDataUrl(blob);
    const stem = String(file.name || "preview").replace(/\.[^.]+$/, "");
    return { dataUrl, name: `${stem}.webp` };
  }
  async function saveItem(payload) {
    const response = await fetch("/visual-eps/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Failed to save item");
    return data;
  }

  function refreshVisualEpsPages(targetPage = null) {
    for (const page of targetPage ? [targetPage] : visualEpsPages()) {
      const button = document.getElementById(`${page.id}_extra_refresh_internal`);
      if (button) button.click();
    }
  }

  async function openEdit(card, trigger) {
    const id = (trigger && trigger.dataset.vepsId) || card.dataset.vepsId;
    if (!id) throw new Error("Visual EPS item id is missing. Reload WebUI and try again.");
    const { item, preview_max_size: previewMaxSize } = await getItem(id);
    const form = document.createElement("form");
    form.className = "veps-edit-form";
    form.innerHTML = `
      <label>Display name override<input name="display_name_override"></label>
      <label><span class="veps-prompt-label">EPS prompt (saved to the YAML file)</span><textarea name="prompt"></textarea></label>
      <label>Prompt to prepend on insert<textarea name="prepend_prompt" placeholder="e.g. masterpiece, best quality"></textarea></label>
      <label>Prompt to append on insert<textarea name="append_prompt" placeholder="e.g. detailed eyes, soft lighting"></textarea></label>
      <label>Negative prompt to append<textarea name="append_negative" placeholder="e.g. low quality, bad anatomy"></textarea></label>
      <label>Tags<input name="tags" placeholder="e.g. hair, pose"></label>
      <label>Memo<textarea name="memo"></textarea></label>
      <label>Reference image<input name="image" type="file" accept="image/png,image/jpeg,image/webp"></label>
      <label class="veps-inline"><input name="clear_image" type="checkbox"> Clear current reference image link</label>
      <div class="veps-current-image"></div>
      <div class="veps-form-actions">
        <button type="submit">Save</button>
        <button type="button" class="veps-modal-close">Cancel</button>
      </div>
      <div class="veps-form-status"></div>
    `;

    form.elements.display_name_override.value = item.display_name_override || "";
    form.elements.prompt.value = item.prompt || "";
    if (!item.prompt_editable) {
      form.elements.prompt.readOnly = true;
      q(".veps-prompt-label", form).textContent = "EPS prompt (read only)";
    }
    form.elements.prepend_prompt.value = item.prepend_prompt || "";
    form.elements.append_prompt.value = item.append_prompt || "";
    form.elements.append_negative.value = item.append_negative || "";
    form.elements.tags.value = Array.isArray(item.tags) ? item.tags.join(", ") : "";
    form.elements.memo.value = item.memo || "";
    const imageBox = q(".veps-current-image", form);
    const imageSrc = cardImage(card);
    imageBox.innerHTML = imageSrc ? `<img src="${imageSrc}" alt=""><span>${item.image || ""}</span>` : "<span>No reference image</span>";

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const status = q(".veps-form-status", form);
      status.textContent = "Saving...";
      try {
        const file = form.elements.image.files[0];
        const imagePayload = await resizeImageFileAsDataUrl(file, previewMaxSize || 384);
        await saveItem({
          id,
          ...(item.prompt_editable ? { prompt: form.elements.prompt.value } : {}),
          display_name_override: form.elements.display_name_override.value,
          prepend_prompt: form.elements.prepend_prompt.value,
          append_prompt: form.elements.append_prompt.value,
          append_negative: form.elements.append_negative.value,
          tags: form.elements.tags.value,
          memo: form.elements.memo.value,
          clear_image: form.elements.clear_image.checked,
          image_data_url: imagePayload.dataUrl,
          image_name: imagePayload.name,
        });
        status.textContent = "Saved. Refreshing cards...";
        refreshVisualEpsPages(pageForCard(card));
        setTimeout(closeModal, 600);
      } catch (error) {
        status.textContent = error.message || String(error);
      }
    });

    openModal(`Visual EPS edit: ${cardTitle(card)}`, form);
  }

  function openPreview(card) {
    const body = document.createElement("div");
    body.className = "veps-preview-modal";
    const imageSrc = cardImage(card);
    body.innerHTML = `
      <div class="veps-large-image">${imageSrc ? `<img src="${imageSrc}" alt="">` : "<div>No Image</div>"}</div>
      <h3>${escapeHtml(cardTitle(card))}</h3>
      <p>${escapeHtml(card.dataset.vepsCategory || "Root")}</p>
      <pre></pre>
    `;
    q("pre", body).textContent = cardDescription(card);
    openModal(cardTitle(card), body);
  }

  function bindCards() {
    for (const page of visualEpsPages()) {
      buildToolbar(page);
    }
    setupLazyImages();
    for (const card of qa(".veps-extra-card:not(.veps-filter-hidden)").slice(0, 40)) {
      loadCardImage(card);
    }
    for (const card of qa(".veps-extra-card")) {
      if (card.dataset.vepsBound === "1") continue;
      card.dataset.vepsBound = "1";
      const edit = q(".veps-edit-button", card);
      const preview = q(".veps-preview-button", card);
      if (edit) {
        edit.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          openEdit(card, edit).catch((error) => alert(error.message || String(error)));
        });
      }
      if (preview) {
        preview.addEventListener("click", (event) => {
          event.preventDefault();
          event.stopPropagation();
          openPreview(card);
        });
      }
    }
    applyFilters();
  }


  function bindOnVisualEpsInteraction(event) {
    const target = event.target instanceof Element ? event.target : null;
    if (!target) return;
    const tabButton = target.closest("button[id$='_visual_eps-button']");
    if (tabButton) {
      const page = document.getElementById(tabButton.id.replace(/-button$/, ""));
      window.setTimeout(() => maybeLoadVisualEpsOnOpen(page), 0);
    }
    if (!target.closest("[id$='_visual_eps'], button, .tab-nav, .tabs")) return;
    window.setTimeout(bindCards, 80);
    window.setTimeout(bindCards, 350);
  }
  document.addEventListener("DOMContentLoaded", bindCards);
  document.addEventListener("gradio:loaded", () => {
    bindCards();
    for (const page of visualEpsPages()) {
      const tabButton = document.getElementById(`${page.id}-button`);
      if (tabButton && tabButton.getAttribute("aria-selected") === "true") {
        maybeLoadVisualEpsOnOpen(page);
      }
    }
  });
  document.addEventListener("click", bindOnVisualEpsInteraction, true);
  document.addEventListener("click", visualEpsTreeClickGuard, true);
})();












