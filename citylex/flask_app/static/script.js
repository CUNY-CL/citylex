document.addEventListener("DOMContentLoaded", function () {
  const selectAllButton = document.getElementById("selectAll");
  const selectNoneButton = document.getElementById("selectNone");
  const sourceCheckboxes = document.querySelectorAll("input[name='sources[]']");
  const fieldCheckboxes = document.querySelectorAll("input[name='fields[]']");
  const licenseCheckboxes = document.querySelectorAll("input[name='licenses']");
  const licenseNames = {
    BY: "CC BY 4.0",
    NC: "CC BY-NC 4.0",
    GNU: "GNU GPL v3",
    apache: "Apache 2.0",
    celex: "CELEX 2 User Agreement",
  };
  const sourceLicenseMap = {
    subtlexus: "NC",
    subtlexuk: "NC",
    UDLexicons: "GNU",
    UniMorph: "BY",
    "WikiPron US": "apache",
    "WikiPron UK": "apache",
    ELP: "NC",
    celexfreq: "celex",
    CELEX_feat: "celex",
    CELEX_pron: "celex",
  };
  const defaultFieldMap = {
    subtlexuk: "subtlexuk_raw_frequency",
    subtlexus: "subtlexus_raw_frequency",
    UDLexicons: "udlex_UDtags",
    UniMorph: "um_UMtags",
    "WikiPron US": "wikipronus_IPA",
    "WikiPron UK": "wikipronuk_IPA",
    ELP: "elp_segmentation",
    celexfreq: "celexfreq_raw_frequency",
    CELEX_feat: "celex_CELEXtags",
    CELEX_pron: "celex_DISC",
  };

  function updateLicenseNotice() {
    const selectedSources = Array.from(sourceCheckboxes).filter(
      (cb) => cb.checked
    );
    const requiredLicenses = new Set(
      selectedSources.map((cb) => sourceLicenseMap[cb.value])
    );
    const licenseNotice = document.getElementById("license-notice");
    if (requiredLicenses.size > 0) {
      const licenseList = Array.from(requiredLicenses)
        .map((license) => {
          const name = licenseNames[license];
          // Set the URL for each license using a switch statement.
          let url = "";
          switch (license) {
            case "BY":
              url = "https://creativecommons.org/licenses/by/4.0/";
              break;
            case "NC":
              url = "https://creativecommons.org/licenses/by-nc/4.0/";
              break;
            case "GNU":
              url = "https://www.gnu.org/licenses/gpl-3.0.html";
              break;
            case "apache":
              url = "https://www.apache.org/licenses/LICENSE-2.0";
              break;
            case "celex":
              url =
                "https://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf";
              break;
            default:
              break;
          }
          // If a URL is set, return the license name wrapped as a hyperlink.
          if (url) {
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${name}</a>`;
          } else {
            return name;
          }
        })
        .join(", ");

      licenseNotice.innerHTML = `By clicking "Generate and Download," you agree to the terms of the following licenses: ${licenseList}`;
    } else {
      licenseNotice.innerHTML = "";
    }
  }

  // Show/hide CELEX password box based on CELEX source selection
  function updateCelexPasswordBox() {
    const celexSources = ["celexfreq", "CELEX_feat", "CELEX_pron"];
    const anyCelexChecked = Array.from(
      document.querySelectorAll("input[name='sources[]']")
    ).some((cb) => celexSources.includes(cb.value) && cb.checked);
    const celexSection = document.getElementById("celex-password-section");
    if (celexSection) {
      celexSection.style.display = anyCelexChecked ? "block" : "none";
    }
  }

  // Call on load and whenever a source is changed
  updateCelexPasswordBox();
  sourceCheckboxes.forEach((cb) => {
    cb.addEventListener("change", updateCelexPasswordBox);
  });

  // Selects all when user clicks "Select All" button
  selectAllButton.addEventListener("click", function () {
    sourceCheckboxes.forEach((checkbox) => (checkbox.checked = true));
    fieldCheckboxes.forEach((checkbox) => (checkbox.checked = true));
    licenseCheckboxes.forEach((checkbox) => (checkbox.checked = true));
    updateLicenseNotice();
  });

  // Deselects all when user clicks "Select None" button
  selectNoneButton.addEventListener("click", function () {
    sourceCheckboxes.forEach((checkbox) => (checkbox.checked = false));
    fieldCheckboxes.forEach((checkbox) => (checkbox.checked = false));
    licenseCheckboxes.forEach((checkbox) => (checkbox.checked = false));
    updateLicenseNotice();
  });

  // Updates the source and license checkboxes based on the field checkboxes
  sourceCheckboxes.forEach((sourceCheckbox) => {
    sourceCheckbox.addEventListener("change", function () {
      const licenseValue = sourceLicenseMap[sourceCheckbox.value];
      const licenseCheckbox = document.querySelector(
        `input[name='licenses'][value='${licenseValue}']`
      );
      const relatedFieldCheckboxes = sourceCheckbox
        .closest("li")
        .querySelectorAll("input[name='fields[]']");
      if (sourceCheckbox.checked) {
        // Check corresponding license checkbox and default subfield when a source is checked
        if (licenseCheckbox) {
          licenseCheckbox.checked = true;
        }
        const defaultFieldValue = defaultFieldMap[sourceCheckbox.value];
        relatedFieldCheckboxes.forEach((fieldCheckbox) => {
          fieldCheckbox.checked = fieldCheckbox.value === defaultFieldValue;
        });
      } else {
        // Uncheck all subfields when source is unchecked
        relatedFieldCheckboxes.forEach(
          (fieldCheckbox) => (fieldCheckbox.checked = false)
        );
      }
      updateLicenseNotice();
    });

    const relatedFieldCheckboxes = sourceCheckbox
      .closest("li")
      .querySelectorAll("input[name='fields[]']");

    // Updates the source checkbox based on the field checkboxes
    function updateSourceCheckbox() {
      const anyFieldChecked = Array.from(relatedFieldCheckboxes).some(
        (field) => field.checked
      );
      sourceCheckbox.checked = anyFieldChecked;
      if (anyFieldChecked) {
        const licenseValue = sourceLicenseMap[sourceCheckbox.value];
        const licenseCheckbox = document.querySelector(
          `input[name='licenses'][value='${licenseValue}']`
        );
        licenseCheckbox.checked = true;
      }
    }
    updateSourceCheckbox();

    // Updates the source checkbox whenever a field checkbox changes
    relatedFieldCheckboxes.forEach((fieldCheckbox) => {
      fieldCheckbox.addEventListener("change", updateSourceCheckbox);
    });
  });

  // Checks the source checkbox when a field checkbox is checked
  fieldCheckboxes.forEach((fieldCheckbox) => {
    fieldCheckbox.addEventListener("change", function () {
      const sourceCheckbox = fieldCheckbox
        .closest("li")
        .querySelector("input[name='sources[]']");
      if (fieldCheckbox.checked) {
        sourceCheckbox.checked = true;
      }
    });
  });

  // Unchecks the source checkbox when a license checkbox is unchecked
  licenseCheckboxes.forEach((licenseCheckbox) => {
    licenseCheckbox.addEventListener("change", function () {
      if (!licenseCheckbox.checked) {
        for (const [source, license] of Object.entries(sourceLicenseMap)) {
          if (license === licenseCheckbox.value) {
            const sourceCheckbox = document.querySelector(
              `input[name='sources[]'][value='${source}']`
            );
            sourceCheckbox.checked = false;
            const fieldCheckboxes = sourceCheckbox
              .closest("li")
              .querySelectorAll("input[name='fields[]']");
            fieldCheckboxes.forEach(
              (fieldCheckbox) => (fieldCheckbox.checked = false)
            );
          }
        }
      }
    });
  });
});
