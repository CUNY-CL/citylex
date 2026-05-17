/**
 * CityLex frontend logic.
 *
 * Responsibilities:
 * 1. Keep source checkboxes, field checkboxes, and license checkboxes in sync
 * — selecting a source auto-selects its default field and its license;
 * deselecting a source clears its fields and (if no other source shares
 * the same license) its license.
 * 2. Show/hide the CELEX password field when CELEX data is selected and the
 * server has indicated a password is required (PASSWORD_SET === true).
 * 3. Render a human-readable license notice below the form.
 */

document.addEventListener("DOMContentLoaded", () => {

  // Element references.

  const btnSelectAll  = document.getElementById("selectAll");
  const btnSelectNone = document.getElementById("selectNone");

  /** @type {NodeListOf<HTMLInputElement>} */
  const sourceCheckboxes  = document.querySelectorAll("input[name='sources[]']");
  /** @type {NodeListOf<HTMLInputElement>} */
  const fieldCheckboxes   = document.querySelectorAll("input[name='fields[]']");
  /** @type {NodeListOf<HTMLInputElement>} */
  const licenseCheckboxes = document.querySelectorAll("input[name='licenses']");

  // Static data.

  /** Human-readable label for each license key. */
  const LICENSE_LABELS = {
    BY:    "CC BY 4.0",
    NC:    "CC BY-NC 4.0",
    SA:    "CC BY-SA 4.0",
    GNU:   "GNU GPL v3",
    celex: "CELEX 2 User Agreement",
  };

  /** License key required by each source. */
  const SOURCE_LICENSE = {
    subtlexUS:   "NC",
    subtlexUK:   "NC",
    UDLexicons:  "GNU",
    UniMorph:    "BY",
    "WikiPron US": "SA",
    "WikiPron UK": "SA",
    ELP:         "NC",
    celexfreq:   "celex",
    celexfeat:   "celex",
    celexpron:   "celex",
  };

  /**
   * The field that gets auto-selected when a source checkbox is first checked.
   * Choosing the most common / most useful field per source keeps the UX
   * predictable without forcing the user to pick one manually.
   */
  const SOURCE_DEFAULT_FIELD = {
    subtlexUK:     "subtlexUK_raw_frequency",
    subtlexUS:     "subtlexUS_raw_frequency",
    UDLexicons:    "udlex_UDtags",
    UniMorph:      "um_UMtags",
    "WikiPron US": "wikipronUS_IPA",
    "WikiPron UK": "wikipronUK_IPA",
    ELP:           "elp_segmentation",
    celexfreq:     "celexfreq_raw_frequency",
    celexfeat:     "celex_CELEXtags",
    celexpron:     "celex_DISC",
  };

  /** Field values that are gated by the CELEX password. */
  const CELEX_FIELD_VALUES = new Set([
    "celexfreq_raw_frequency",
    "celexfreq_freq_per_million",
    "celexfreq_logprob",
    "celexfreq_zipf",
    "celex_UDtags",
    "celex_UMtags",
    "celex_CELEXtags",
    "celex_DISC",
  ]);

  // License notice.

  /**
   * Rebuilds the license notice based on which sources are currently checked.
   * Only sources that are actually selected contribute a license entry.
   */
  function updateLicenseNotice() {
    const checkedSources = Array.from(sourceCheckboxes).filter(cb => cb.checked);
    const licenseKeys    = new Set(checkedSources.map(cb => SOURCE_LICENSE[cb.value]));
    const noticeEl       = document.getElementById("license-notice");

    if (licenseKeys.size === 0) {
      noticeEl.innerHTML = "";
      return;
    }

    const licenseLinks = Array.from(licenseKeys).map(key => {
      const label = LICENSE_LABELS[key];
      const urls  = {
        BY:    "https://creativecommons.org/licenses/by/4.0/",
        NC:    "https://creativecommons.org/licenses/by-nc/4.0/",
        SA:    "https://creativecommons.org/licenses/by-sa/4.0/",
        GNU:   "https://www.gnu.org/licenses/gpl-3.0.en.html",
        celex: "https://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf",
      };
      const url = urls[key];
      return url
        ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label;
    });

    noticeEl.innerHTML =
      `By clicking "Generate and Download," you agree to the terms of the ` +
      `following licenses: ${licenseLinks.join(", ")}`;
  }

  // CELEX password field visibility.

  /**
   * Shows or hides the CELEX password input depending on whether any CELEX
   * field is selected.  Does nothing if the server hasn't set a password
   * (PASSWORD_SET is injected by the Flask template).
   */
  function updatePasswordVisibility() {
    if (typeof PASSWORD_SET === "undefined" || !PASSWORD_SET) return;

    const anyCelexField = Array.from(fieldCheckboxes).some(
      cb => CELEX_FIELD_VALUES.has(cb.value) && cb.checked
    );
    const section = document.getElementById("celex-password-section");
    if (section) section.style.display = anyCelexField ? "block" : "none";
  }

  // Source/field/license synchronisation.

  /**
   * Called when a source checkbox changes state.
   * - On check:   tick the source's default field and its license.
   * - On uncheck: untick all of the source's fields.
   * Then update the derived UI (license notice, password field).
   *
   * @param {HTMLInputElement} sourceCheckbox
   */
  function onSourceChange(sourceCheckbox) {
    const sourceValue  = sourceCheckbox.value;
    const licenseKey   = SOURCE_LICENSE[sourceValue];
    const licenseInput = document.querySelector(
      `input[name='licenses'][value='${licenseKey}']`
    );
    const fieldInputs  = sourceCheckbox
      .closest("li")
      .querySelectorAll("input[name='fields[]']");

    if (sourceCheckbox.checked) {
      // Tick the license.
      if (licenseInput) licenseInput.checked = true;
      // Auto-select only the default field; leave the rest untouched.
      const defaultFieldValue = SOURCE_DEFAULT_FIELD[sourceValue];
      fieldInputs.forEach(fi => {
        fi.checked = fi.value === defaultFieldValue;
      });
    } else {
      // Untick all fields belonging to this source.
      fieldInputs.forEach(fi => { fi.checked = false; });
    }

    updateLicenseNotice();
    updatePasswordVisibility();
  }

  /**
   * Called when a field checkbox changes state.
   * Ensures the parent source checkbox mirrors whether *any* of its fields
   * are checked, and keeps the license in sync.
   *
   * @param {HTMLInputElement} fieldCheckbox
   */
  function onFieldChange(fieldCheckbox) {
    const sourceItem   = fieldCheckbox.closest("ul")?.closest("li");
    const sourceInput  = sourceItem?.querySelector("input[name='sources[]']");
    if (!sourceInput) return;

    const siblingFields = sourceItem.querySelectorAll("input[name='fields[]']");
    const anyChecked    = Array.from(siblingFields).some(fi => fi.checked);

    sourceInput.checked = anyChecked;

    if (anyChecked) {
      const licenseKey   = SOURCE_LICENSE[sourceInput.value];
      const licenseInput = document.querySelector(
        `input[name='licenses'][value='${licenseKey}']`
      );
      if (licenseInput) licenseInput.checked = true;
    }

    updateLicenseNotice();
    updatePasswordVisibility();
  }

  /**
   * Called when a license checkbox is manually unchecked.
   * Deselects every source (and its fields) that requires this license.
   *
   * @param {HTMLInputElement} licenseCheckbox
   */
  function onLicenseUncheck(licenseCheckbox) {
    if (licenseCheckbox.checked) return;

    for (const [sourceValue, licenseKey] of Object.entries(SOURCE_LICENSE)) {
      if (licenseKey !== licenseCheckbox.value) continue;
      const sourceInput = document.querySelector(
        `input[name='sources[]'][value='${sourceValue}']`
      );
      if (!sourceInput) continue;
      sourceInput.checked = false;
      sourceInput
        .closest("li")
        .querySelectorAll("input[name='fields[]']")
        .forEach(fi => { fi.checked = false; });
    }

    updatePasswordVisibility();
  }

  // Select-all / select-none buttons.

  btnSelectAll.addEventListener("click", () => {
    sourceCheckboxes .forEach(cb => { cb.checked = true; });
    fieldCheckboxes  .forEach(cb => { cb.checked = true; });
    licenseCheckboxes.forEach(cb => { cb.checked = true; });
    updateLicenseNotice();
    updatePasswordVisibility();
  });

  btnSelectNone.addEventListener("click", () => {
    sourceCheckboxes .forEach(cb => { cb.checked = false; });
    fieldCheckboxes  .forEach(cb => { cb.checked = false; });
    licenseCheckboxes.forEach(cb => { cb.checked = false; });
    updateLicenseNotice();
    updatePasswordVisibility();
  });

  // Attach listeners.

  sourceCheckboxes .forEach(cb => cb.addEventListener("change", () => onSourceChange(cb)));
  fieldCheckboxes  .forEach(cb => cb.addEventListener("change", () => onFieldChange(cb)));
  licenseCheckboxes.forEach(cb => cb.addEventListener("change", () => onLicenseUncheck(cb)));

  // Initializes derived state to match whatever the page loads with.
  updateLicenseNotice();
  updatePasswordVisibility();

});
