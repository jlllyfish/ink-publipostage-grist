// Variables globales
let quill;
let currentTable = "";
let currentColumns = [];
let sampleRecord = {};
let allRecords = [];
let allRecordsUnfiltered = [];
let currentLogo = null;
let currentServiceName = "";
let currentSignature = null;

// 🆕 NOUVELLES VARIABLES POUR GRIST CONFIG
let gristApiKey = "";
let gristDocId = "";

// Variables pour le filtre
let filterEnabled = false;
let filterColumnName = "Pdf_print";
let filteredRecordsCount = 0;
let totalRecordsCount = 0;

// Initialisation
document.addEventListener("DOMContentLoaded", () => {
  // Configuration Quill avec formats personnalisés
  if (typeof Quill !== "undefined") {
    const Size = Quill.import("formats/size");
    Size.whitelist = ["small", false, "large", "huge"];
    Quill.register(Size, true);

    quill = new Quill("#editor", {
      theme: "snow",
      modules: {
        toolbar: [
          [{ size: ["small", false, "large", "huge"] }],
          ["bold", "italic", "underline"],
          [{ list: "ordered" }, { list: "bullet" }],
          [{ align: [] }],
          [{ color: [] }, { background: [] }],
          ["clean"],
        ],
      },
      placeholder:
        "Commencez à écrire votre document ici...\n\nUtilisez les outils de mise en forme et cliquez sur les badges bleus pour insérer les champs dynamiques.",
    });
  }

  // 🆕 CHARGER LA CONFIG GRIST DEPUIS LOCALSTORAGE
  loadGristConfig();

  // Initialisation de l'application
  testConnection();
  loadTables();
  loadTemplatesList();
  loadFilterColumnName();

  // Événements
  const filenameInput = document.getElementById("filenamePattern");
  if (filenameInput) {
    filenameInput.addEventListener("input", updateFilenamePreview);
  }

  // Initialiser les accordéons
  initializeAccordions();

  // Initialiser DSFR si disponible
  if (window.dsfr) {
    try {
      window.dsfr.start();
      console.log("✅ DSFR initialisé");
    } catch (error) {
      console.warn("⚠️ DSFR non critique:", error);
    }
  }
});

// ===== 🆕 GESTION DE LA CONFIG GRIST =====

function saveGristConfig() {
  const apiKeyInput = document.getElementById("gristApiKey");
  const docIdInput = document.getElementById("gristDocId");

  if (apiKeyInput) gristApiKey = apiKeyInput.value;
  if (docIdInput) gristDocId = docIdInput.value;

  // 🆕 Sauvegarder dans sessionStorage (perdu à la fermeture de l'onglet)
  try {
    sessionStorage.setItem("gristApiKey", gristApiKey);
    sessionStorage.setItem("gristDocId", gristDocId);
    showNotification("Configuration Grist enregistrée pour cette session", "success");
  } catch (e) {
    console.warn("SessionStorage non disponible");
  }
}

function loadGristConfig() {
  // 🆕 Charger depuis sessionStorage
  try {
    const savedApiKey = sessionStorage.getItem("gristApiKey");
    const savedDocId = sessionStorage.getItem("gristDocId");

    if (savedApiKey) {
      gristApiKey = savedApiKey;
      const apiKeyInput = document.getElementById("gristApiKey");
      if (apiKeyInput) apiKeyInput.value = savedApiKey;
    }

    if (savedDocId) {
      gristDocId = savedDocId;
      const docIdInput = document.getElementById("gristDocId");
      if (docIdInput) docIdInput.value = savedDocId;
    }
  } catch (e) {
    console.warn("SessionStorage non disponible");
  }
}

// 🆕 VALIDATION DES IMAGES
function validateImageFile(file) {
  const allowedTypes = ["image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"];
  const maxSize = 5 * 1024 * 1024; // 5 MB

  if (!allowedTypes.includes(file.type)) {
    showNotification("Format d'image non autorisé. Utilisez PNG, JPEG, GIF ou WebP.", "error");
    return false;
  }

  if (file.size > maxSize) {
    showNotification("Image trop volumineuse (max 5 MB)", "error");
    return false;
  }

  return true;
}

async function testGristConnection() {
  if (!gristApiKey || !gristDocId) {
    showNotification("Veuillez saisir la clé API et le Doc ID", "warning");
    return;
  }

  try {
    showLoadingModal("Test de connexion...");

    const response = await fetch("/api/test-connection", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    const data = await response.json();

    const status = document.getElementById("connectionStatus");
    if (status) {
      if (data.success) {
        status.innerHTML = "✅ Connecté à Grist";
        status.className = "fr-badge fr-badge--success";
        showNotification("Connexion réussie", "success");
      } else {
        status.innerHTML = "❌ Échec connexion";
        status.className = "fr-badge fr-badge--error";
        showNotification(data.message || "Erreur de connexion", "error");
      }
    }
  } catch (error) {
    console.error("Erreur test connexion:", error);
    showNotification("Erreur lors du test de connexion", "error");
  } finally {
    hideLoadingModal();
  }
}

// ===== GESTION DES ACCORDÉONS =====

function initializeAccordions() {
  const accordionButtons = document.querySelectorAll(".fr-accordion__btn");

  accordionButtons.forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();

      const targetId = this.getAttribute("aria-controls");
      const targetPanel = document.getElementById(targetId);

      if (targetPanel) {
        const isExpanded = this.getAttribute("aria-expanded") === "true";

        // Toggle l'état
        if (isExpanded) {
          // Fermer l'accordéon
          this.setAttribute("aria-expanded", "false");
          targetPanel.classList.remove("fr-collapse--expanded");
        } else {
          // Ouvrir l'accordéon
          this.setAttribute("aria-expanded", "true");
          targetPanel.classList.add("fr-collapse--expanded");
          // Retirer le style inline si présent
          targetPanel.style.display = "";
        }
      }
    });
  });

  // Retirer tous les styles display:none inline au démarrage
  document.querySelectorAll(".fr-collapse").forEach((collapse) => {
    if (collapse.style.display === "none") {
      collapse.style.display = "";
    }
  });
}

// ===== GESTION DES ONGLETS =====

function switchTab(tabName) {
  // Retirer la classe active de tous les onglets
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.remove("active");
  });

  // Masquer tous les panneaux
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.remove("active");
  });

  // Activer l'onglet sélectionné
  event.target.classList.add("active");

  // Afficher le panneau correspondant
  const panel = document.getElementById(tabName + "Tab");
  if (panel) {
    panel.classList.add("active");

    // Actions spécifiques selon l'onglet
    if (tabName === "preview") {
      generatePreview();
    } else if (tabName === "code") {
      updateHTMLCode();
    }
  }
}

// ===== TEST DE CONNEXION =====

async function testConnection() {
  // 🆕 UTILISER LA FONCTION AVEC CONFIG
  if (gristApiKey && gristDocId) {
    await testGristConnection();
  } else {
    const status = document.getElementById("connectionStatus");
    if (status) {
      status.innerHTML = "⚠️ Config manquante";
      status.className = "fr-badge fr-badge--warning";
    }
  }
}

// ===== GESTION DES TABLES =====

async function loadTables() {
  // 🆕 VÉRIFIER LA CONFIG AVANT
  if (!gristApiKey || !gristDocId) {
    showNotification("Veuillez configurer l'API Grist d'abord", "warning");
    return;
  }

  try {
    const response = await fetch("/api/tables", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    const data = await response.json();

    if (data.success) {
      const select = document.getElementById("tableSelect");
      if (select) {
        select.innerHTML = '<option value="">Sélectionner...</option>';

        data.tables.forEach((table) => {
          const option = document.createElement("option");
          option.value = table.id;
          option.textContent = table.id;
          select.appendChild(option);
        });
      }
    } else {
      showNotification(data.message || "Erreur lors du chargement des tables", "error");
    }
  } catch (error) {
    showNotification("Erreur lors du chargement des tables", "error");
  }
}

async function loadColumns() {
  const tableId = document.getElementById("tableSelect").value;
  if (!tableId) return;

  // 🆕 VÉRIFIER LA CONFIG
  if (!gristApiKey || !gristDocId) {
    showNotification("Configuration Grist manquante", "warning");
    return;
  }

  currentTable = tableId;

  try {
    showLoadingModal("Chargement des colonnes...");

    const response = await fetch(`/api/columns/${tableId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    const data = await response.json();

    if (data.success) {
      currentColumns = data.columns;
      displayFields(data.columns);
      await loadRecords();
    } else {
      showNotification("Erreur lors du chargement des colonnes", "error");
    }
  } catch (error) {
    showNotification("Erreur lors du chargement des colonnes", "error");
  } finally {
    hideLoadingModal();
  }
}

function displayFields(columns) {
  const container = document.getElementById("fieldsContainer");
  if (!container) return;

  container.innerHTML = "";

  columns.forEach((column) => {
    const badge = document.createElement("span");
    badge.className = "field-badge";
    // Les colonnes sont déjà des strings, pas des objets
    const fieldName = typeof column === "string" ? column : column.id;
    badge.textContent = fieldName;
    badge.onclick = () => insertField(fieldName);
    badge.tabIndex = 0;
    badge.onkeypress = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        insertField(fieldName);
      }
    };
    container.appendChild(badge);
  });
}

// ===== GESTION DES ENREGISTREMENTS =====

async function loadRecords() {
  const tableId = document.getElementById("tableSelect").value;
  if (!tableId) return;

  // 🆕 VÉRIFIER LA CONFIG
  if (!gristApiKey || !gristDocId) {
    showNotification("Configuration Grist manquante", "warning");
    return;
  }

  try {
    showLoadingModal("Chargement des données...");

    const response = await fetch(`/api/records/${tableId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    const data = await response.json();

    if (data.success) {
      allRecordsUnfiltered = data.records;
      applyFilter();
      populateRecordSelect();

      if (allRecords.length > 0) {
        sampleRecord = allRecords[0];
        displaySampleData();
      }
    }
  } catch (error) {
    showNotification("Erreur lors du chargement des données", "error");
  } finally {
    hideLoadingModal();
  }
}

function applyFilter() {
  if (filterEnabled && filterColumnName) {
    allRecords = allRecordsUnfiltered.filter(
      (record) => record[filterColumnName] === true || record[filterColumnName] === 1
    );
  } else {
    allRecords = [...allRecordsUnfiltered];
  }

  totalRecordsCount = allRecordsUnfiltered.length;
  filteredRecordsCount = allRecords.length;
  updateFilterCount();
}

function updateFilterCount() {
  const countElement = document.getElementById("filteredCount");
  if (countElement) {
    countElement.textContent = `${filteredRecordsCount}/${totalRecordsCount}`;
  }
}

function populateRecordSelect() {
  const select = document.getElementById("recordSelect");
  if (!select) return;

  select.innerHTML = '<option value="">Sélectionner...</option>';

  allRecords.forEach((record, index) => {
    const option = document.createElement("option");
    option.value = index;
    const label = record.id || record.ID || record.Name || record.name || `Ligne ${index + 1}`;
    option.textContent = label;
    select.appendChild(option);
  });
}

function selectRecord() {
  const select = document.getElementById("recordSelect");
  if (!select) return;

  const index = select.value;
  if (index !== "" && allRecords[index]) {
    sampleRecord = allRecords[index];
    displaySampleData();
  }
}

function displaySampleData() {
  const container = document.getElementById("sampleData");
  if (!container) return;

  container.innerHTML = "";

  for (const [key, value] of Object.entries(sampleRecord)) {
    const row = document.createElement("div");
    row.className = "data-row";

    const label = document.createElement("div");
    label.className = "data-label";
    label.textContent = key;

    const valueDiv = document.createElement("div");
    valueDiv.className = "data-value";
    valueDiv.textContent = value !== null && value !== undefined ? String(value) : "";

    row.appendChild(label);
    row.appendChild(valueDiv);
    container.appendChild(row);
  }
}

// ===== INSERTION DE CHAMP =====

function insertField(fieldName) {
  if (!quill) return;

  const selection = quill.getSelection();
  if (selection) {
    quill.insertText(selection.index, `{{${fieldName}}}`, "user");
    quill.setSelection(selection.index + fieldName.length + 4);
  } else {
    const length = quill.getLength();
    quill.insertText(length - 1, `{{${fieldName}}}`, "user");
  }
  showNotification(`Champ "${fieldName}" inséré`, "success");
}

// ===== GESTION DES FILTRES =====

function toggleFilter() {
  const checkbox = document.getElementById("filterEnabled");
  if (!checkbox) return;

  filterEnabled = checkbox.checked;
  applyFilter();
  populateRecordSelect();
  showNotification(filterEnabled ? "Filtre activé" : "Filtre désactivé", "info");
}

function updateFilterColumn() {
  const input = document.getElementById("filterColumn");
  if (!input) return;

  filterColumnName = input.value;
  const nameElement = document.getElementById("filterColumnName");
  if (nameElement) {
    nameElement.textContent = filterColumnName;
  }
  saveFilterColumnName();
  applyFilter();
  populateRecordSelect();
}

function saveFilterColumnName() {
  try {
    localStorage.setItem("filterColumnName", filterColumnName);
  } catch (e) {
    console.warn("LocalStorage non disponible");
  }
}

function loadFilterColumnName() {
  try {
    const saved = localStorage.getItem("filterColumnName");
    if (saved) {
      filterColumnName = saved;
      const input = document.getElementById("filterColumn");
      if (input) input.value = saved;
      const nameElement = document.getElementById("filterColumnName");
      if (nameElement) nameElement.textContent = saved;
    }
  } catch (e) {
    console.warn("LocalStorage non disponible");
  }
}

// ===== GESTION DES IMAGES =====

function handleLogo(event) {
  const file = event.target.files[0];
  if (file) {
    // 🆕 VALIDER AVANT
    if (!validateImageFile(file)) {
      event.target.value = ""; // Reset input
      return;
    }

    const reader = new FileReader();
    reader.onload = function (e) {
      currentLogo = e.target.result;
      const preview = document.getElementById("logoPreview");
      if (preview) {
        preview.innerHTML = `<img src="${currentLogo}" alt="Logo" style="max-height: 60px;">`;
      }
    };
    reader.readAsDataURL(file);
  }
}

function handleSignature(event) {
  const file = event.target.files[0];
  if (file) {
    // 🆕 VALIDER AVANT
    if (!validateImageFile(file)) {
      event.target.value = ""; // Reset input
      return;
    }
    const reader = new FileReader();
    reader.onload = function (e) {
      currentSignature = e.target.result;
      const preview = document.getElementById("signaturePreview");
      if (preview) {
        preview.innerHTML = `<img src="${currentSignature}" alt="Signature" style="max-height: 60px;">`;
      }
    };
    reader.readAsDataURL(file);
  }
}

function updateServiceName() {
  const input = document.getElementById("serviceName");
  if (input) {
    currentServiceName = input.value;
  }
}

// ===== GESTION DU NOM DE FICHIER =====

function updateFilenamePreview() {
  const input = document.getElementById("filenamePattern");
  if (!input) return;

  const pattern = input.value || "document_{id}";
  let preview = pattern;

  if (sampleRecord) {
    for (const [key, value] of Object.entries(sampleRecord)) {
      const regex = new RegExp(`\\{${key}\\}`, "g");
      preview = preview.replace(regex, value || "");
    }
  } else {
    preview = preview.replace(/\{[^}]+\}/g, "[valeur]");
  }

  const previewElement = document.getElementById("filenamePreview");
  if (previewElement) {
    previewElement.innerHTML = `<code>${preview}.pdf</code>`;
  }
}

// ===== GÉNÉRATION D'APERÇU =====

async function generatePreview() {
  if (!currentTable) {
    showNotification("Veuillez d'abord sélectionner une table", "warning");
    return;
  }

  if (!quill) {
    showNotification("Editeur non initialisé", "error");
    return;
  }

  try {
    showLoadingModal("Génération de l'aperçu...");

    const htmlContent = quill.root.innerHTML;
    const cssContent = document.getElementById("cssEditor")?.value || "";

    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_content: htmlContent,
        template_css: cssContent,
        record_data: sampleRecord,
        logo: currentLogo,
        service_name: currentServiceName,
        signature: currentSignature,
      }),
    });

    const data = await response.json();

    if (data.success) {
      const iframe = document.getElementById("previewFrame");
      if (iframe) {
        iframe.srcdoc = data.html;
      }
    } else {
      showNotification("Erreur lors de la génération de l'aperçu", "error");
    }
  } catch (error) {
    showNotification("Erreur lors de la génération de l'aperçu", "error");
  } finally {
    hideLoadingModal();
  }
}

// ===== AFFICHAGE DU CODE HTML =====

function updateHTMLCode() {
  if (!quill) return;

  const htmlContent = quill.root.innerHTML;
  const codeElement = document.getElementById("htmlCode");

  if (codeElement) {
    // Formatter le HTML pour une meilleure lisibilité
    const formatted = formatHTML(htmlContent);
    codeElement.textContent = formatted;
  }
}

function formatHTML(html) {
  // Formatage basique du HTML
  let formatted = html.replace(/></g, ">\n<").replace(/(\w+)="([^"]*)"/g, '\n    $1="$2"');

  return formatted;
}

function copyHTMLCode() {
  const codeElement = document.getElementById("htmlCode");
  if (!codeElement) return;

  const code = codeElement.textContent;
  navigator.clipboard
    .writeText(code)
    .then(() => {
      showNotification("Code copié dans le presse-papiers", "success");
    })
    .catch(() => {
      showNotification("Erreur lors de la copie", "error");
    });
}

// ===== GÉNÉRATION DE PDF =====

async function generatePDF() {
  if (!currentTable || !sampleRecord) {
    showNotification("Veuillez sélectionner une table et un enregistrement", "warning");
    return;
  }

  if (!quill) {
    showNotification("Editeur non initialisé", "error");
    return;
  }

  try {
    showLoadingModal("Génération du PDF...");

    const htmlContent = quill.root.innerHTML;
    const cssContent = document.getElementById("cssEditor")?.value || "";
    const filenamePattern = document.getElementById("filenamePattern")?.value || "document_{id}";

    const response = await fetch("/api/generate-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_content: htmlContent,
        template_css: cssContent,
        record_data: sampleRecord,
        filename_pattern: filenamePattern,
        logo: currentLogo,
        service_name: currentServiceName,
        signature: currentSignature,
        // 🆕 AJOUTER LA CONFIG
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    if (!response.ok) {
      throw new Error("Erreur lors de la génération");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = generateFilename(sampleRecord, filenamePattern) + ".pdf";
    a.click();
    window.URL.revokeObjectURL(url);

    showNotification("PDF généré avec succès", "success");
  } catch (error) {
    showNotification("Erreur lors de la génération du PDF", "error");
  } finally {
    hideLoadingModal();
  }
}

async function generateMultiplePDF() {
  if (!currentTable || allRecords.length === 0) {
    showNotification("Aucune donnée à traiter", "warning");
    return;
  }

  if (!quill) {
    showNotification("Editeur non initialisé", "error");
    return;
  }

  const confirmGenerate = confirm(
    `Générer ${allRecords.length} PDF ? Cette opération peut prendre du temps.`
  );

  if (!confirmGenerate) return;

  try {
    showLoadingModal(`Génération de ${allRecords.length} PDF...`);

    const htmlContent = quill.root.innerHTML;
    const cssContent = document.getElementById("cssEditor")?.value || "";
    const filenamePattern = document.getElementById("filenamePattern")?.value || "document_{id}";

    const response = await fetch("/api/generate-multiple", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table_id: currentTable,
        template_content: htmlContent,
        template_css: cssContent,
        apply_filter: filterEnabled,
        filename_pattern: filenamePattern,
        logo: currentLogo,
        service_name: currentServiceName,
        signature: currentSignature,
        // 🆕 AJOUTER LA CONFIG
        api_key: gristApiKey,
        doc_id: gristDocId,
      }),
    });

    if (!response.ok) {
      throw new Error("Erreur lors de la génération");
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `publipostage_${currentTable}_${new Date().getTime()}.zip`;
    a.click();
    window.URL.revokeObjectURL(url);

    showNotification(`${allRecords.length} PDF générés avec succès`, "success");
  } catch (error) {
    showNotification("Erreur lors de la génération des PDF", "error");
  } finally {
    hideLoadingModal();
  }
}

function generateFilename(record, pattern) {
  let filename = pattern;
  for (const [key, value] of Object.entries(record)) {
    const regex = new RegExp(`\\{${key}\\}`, "g");
    filename = filename.replace(regex, value || "");
  }
  // Nettoyer le nom de fichier
  filename = filename.replace(/[^a-zA-Z0-9_-]/g, "_");
  return filename;
}

// ===== GESTION DES TEMPLATES =====

async function saveTemplate() {
  const templateName = prompt("Nom du template :");
  if (!templateName || !quill) return;

  try {
    const htmlContent = quill.root.innerHTML;
    const cssContent = document.getElementById("cssEditor")?.value || "";

    const response = await fetch("/api/save-template", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        template_name: templateName,
        template_content: htmlContent,
        logo: currentLogo,
        signature: currentSignature,
        service_name: currentServiceName,
        template_css: cssContent,
        table_id: currentTable,
      }),
    });

    const data = await response.json();

    if (data.success) {
      showNotification("Template sauvegardé avec succès", "success");
      loadTemplatesList();
    } else {
      showNotification("Erreur lors de la sauvegarde", "error");
    }
  } catch (error) {
    showNotification("Erreur lors de la sauvegarde", "error");
  }
}

async function loadTemplatesList() {
  try {
    const response = await fetch("/api/templates");
    const data = await response.json();

    if (data.success) {
      const container = document.getElementById("templatesList");
      if (!container) return;

      container.innerHTML = "";

      if (data.templates.length === 0) {
        container.innerHTML = '<p class="fr-text--sm">Aucun template sauvegardé</p>';
        return;
      }

      data.templates.forEach((templateName) => {
        const item = document.createElement("div");
        item.className = "template-item";

        // Nom cliquable du template
        const nameSpan = document.createElement("span");
        nameSpan.textContent = templateName;
        nameSpan.style.cursor = "pointer";
        nameSpan.onclick = () => loadTemplate(templateName);

        // Bouton supprimer
        const deleteBtn = document.createElement("button");
        deleteBtn.textContent = "×";
        deleteBtn.className = "delete-template-btn";
        deleteBtn.title = "Supprimer ce template";
        deleteBtn.onclick = (e) => {
          e.stopPropagation(); // empêche le chargement
          deleteTemplate(templateName);
        };

        item.appendChild(nameSpan);
        item.appendChild(deleteBtn);
        container.appendChild(item);
      });
    }
  } catch (error) {
    console.error("Erreur lors du chargement des templates:", error);
    showNotification("Erreur lors du chargement des templates", "error");
  }
}

// Charger un template (avec encodage pour accents/espaces)
async function loadTemplate(templateName) {
  if (!quill) return;

  try {
    showLoadingModal("Chargement du template...");

    const response = await fetch("/api/load-template/" + templateName.replace(/ /g, "_"));
    const data = await response.json();

    if (data.success) {
      const template = data.template;
      quill.root.innerHTML = template.template_content || "";
      const cssEditor = document.getElementById("cssEditor");
      if (cssEditor) {
        cssEditor.value = data.template.template_css || "";
      }

      // Logo
      const logoPreview = document.getElementById("logoPreview");
      if (data.template.logo) {
        currentLogo = data.template.logo;
        if (logoPreview) {
          // Affiche le logo
          logoPreview.innerHTML = `<img src="${currentLogo}" alt="Logo" style="max-height: 60px;">`;
        }
      } else {
        currentLogo = null;
        if (logoPreview) {
          // Supprime l'affichage
          logoPreview.innerHTML = "Aucun logo";
        }
      }

      // Signature
      const signaturePreview = document.getElementById("signaturePreview");
      if (data.template.signature) {
        currentSignature = data.template.signature;
        if (signaturePreview) {
          // Affiche la signature
          signaturePreview.innerHTML = `<img src="${currentSignature}" alt="Signature" style="max-height: 60px;">`;
        }
      } else {
        currentSignature = null;
        if (signaturePreview) {
          // Supprime l'affichage
          signaturePreview.innerHTML = "Aucune signature";
        }
      }

      // Table associée
      if (data.template.table_id) {
        const tableSelect = document.getElementById("tableSelect");
        if (tableSelect) {
          tableSelect.value = data.template.table_id;
          await loadColumns();
        }
      }

      showNotification(`Template "${templateName}" chargé avec succès`, "success");
    } else {
      showNotification("Erreur lors du chargement du template", "error");
    }
  } catch (error) {
    console.error(error);
    showNotification("Erreur lors du chargement du template", "error");
  } finally {
    hideLoadingModal();
  }
}

async function deleteTemplate(templateName) {
  if (!confirm(`Supprimer le template "${templateName}" ?`)) return;

  try {
    const response = await fetch(`/api/delete-template/${templateName}`, {
      method: "DELETE",
    });

    const data = await response.json();

    if (data.success) {
      showNotification("Template supprimé", "success");
      loadTemplatesList();
    } else {
      showNotification("Erreur lors de la suppression", "error");
    }
  } catch (error) {
    showNotification("Erreur lors de la suppression", "error");
  }
}

// ===== MODALES ET NOTIFICATIONS =====

function showLoadingModal(message = "Chargement...") {
  const modal = document.getElementById("loadingModal");
  const messageElement = document.getElementById("loadingMessage");
  const titleElement = document.getElementById("loading-title");

  if (messageElement) messageElement.textContent = message;
  if (titleElement)
    titleElement.textContent = message.includes("PDF") ? "Génération en cours..." : "Chargement...";

  if (modal && modal.showModal) {
    modal.showModal();
  }
}

function hideLoadingModal() {
  const modal = document.getElementById("loadingModal");
  if (modal && modal.close) {
    modal.close();
  }
}

function showNotification(message, type = "info") {
  const notification = document.getElementById("notification");
  const messageElement = document.getElementById("notificationMessage");

  if (!notification || !messageElement) return;

  // Définir le type de notification
  notification.className = "notification-toast " + type;

  messageElement.textContent = message;
  notification.style.display = "block";

  // Masquer après 4 secondes
  setTimeout(() => {
    notification.style.display = "none";
  }, 4000);
}

// ===== RACCOURCIS CLAVIER =====

document.addEventListener("keydown", (e) => {
  // Ctrl+S pour sauvegarder
  if (e.ctrlKey && e.key === "s") {
    e.preventDefault();
    saveTemplate();
  }

  // Ctrl+P pour aperçu
  if (e.ctrlKey && e.key === "p") {
    e.preventDefault();
    switchTab("preview");
  }
});

// Fonction globale pour éviter les erreurs
window.loadTemplate = loadTemplate;
window.deleteTemplate = deleteTemplate;
