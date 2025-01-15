document.addEventListener("DOMContentLoaded", function() {
    const selectAllButton = document.getElementById("selectAll");
    const selectNoneButton = document.getElementById("selectNone");
    const sourceCheckboxes = document.querySelectorAll("input[name='sources[]']");
    const fieldCheckboxes = document.querySelectorAll("input[name='fields[]']");
    const licenseCheckboxes = document.querySelectorAll("input[name='licenses']");
    const sourceLicenseMap = {
      "SUBTLEX-UK": "NC",
      "SUBTLEX-US": "NC",
      "UDLexicons": "GNU",
      "UniMorph": "BY",
      "WikiPron-US": "apache",
      "WikiPron-UK": "apache",
      "ELP": "NC"
    };
  
    // Selects all when user clicks "Select All" button
    selectAllButton.addEventListener("click", function() {
      sourceCheckboxes.forEach(checkbox => checkbox.checked = true);
      fieldCheckboxes.forEach(checkbox => checkbox.checked = true);
      licenseCheckboxes.forEach(checkbox => checkbox.checked = true);
    });
  
    // Deselects all when user clicks "Select None" button
    selectNoneButton.addEventListener("click", function() {
      sourceCheckboxes.forEach(checkbox => checkbox.checked = false);
      fieldCheckboxes.forEach(checkbox => checkbox.checked = false);
      licenseCheckboxes.forEach(checkbox => checkbox.checked = false);
    });
  
    // Updates the source and license checkboxes based on the field checkboxes
    sourceCheckboxes.forEach(sourceCheckbox => {
      sourceCheckbox.addEventListener("change", function() {
        const licenseValue = sourceLicenseMap[sourceCheckbox.value];
        const licenseCheckbox = document.querySelector(`input[name='licenses'][value='${licenseValue}']`);
        const relatedFieldCheckboxes = sourceCheckbox.closest('li').querySelectorAll("input[name='fields[]']");
        if (sourceCheckbox.checked) {
          licenseCheckbox.checked = true;
          relatedFieldCheckboxes.forEach(fieldCheckbox => fieldCheckbox.checked = true);
        } else {
          relatedFieldCheckboxes.forEach(fieldCheckbox => fieldCheckbox.checked = false);
        }
      });
      
      const relatedFieldCheckboxes = sourceCheckbox.closest('li').querySelectorAll("input[name='fields[]']");
      
      // Updates the source checkbox based on the field checkboxes
      function updateSourceCheckbox() {
        const anyFieldChecked = Array.from(relatedFieldCheckboxes).some(field => field.checked);
        sourceCheckbox.checked = anyFieldChecked;
        if (anyFieldChecked) {
          const licenseValue = sourceLicenseMap[sourceCheckbox.value];
          const licenseCheckbox = document.querySelector(`input[name='licenses'][value='${licenseValue}']`);
          licenseCheckbox.checked = true;
        }
      }
      updateSourceCheckbox();
      
      // Updates the source checkbox whenever a field checkbox changes
      relatedFieldCheckboxes.forEach(fieldCheckbox => {
        fieldCheckbox.addEventListener("change", updateSourceCheckbox);
      });
    });
  
    // Checks the source checkbox when a field checkbox is checked
    fieldCheckboxes.forEach(fieldCheckbox => {
      fieldCheckbox.addEventListener("change", function() {
        const sourceCheckbox = fieldCheckbox.closest('li').querySelector("input[name='sources[]']");
        if (fieldCheckbox.checked) {
          sourceCheckbox.checked = true;
        }
      });
    });
  
    // Unchecks the source checkbox when a license checkbox is unchecked
    licenseCheckboxes.forEach(licenseCheckbox => {
      licenseCheckbox.addEventListener("change", function() {
        if (!licenseCheckbox.checked) {
          for (const [source, license] of Object.entries(sourceLicenseMap)) {
            if (license === licenseCheckbox.value) {
              const sourceCheckbox = document.querySelector(`input[name='sources[]'][value='${source}']`);
              sourceCheckbox.checked = false;
              const fieldCheckboxes = sourceCheckbox.closest('li').querySelectorAll("input[name='fields[]']");
              fieldCheckboxes.forEach(fieldCheckbox => fieldCheckbox.checked = false);
            }
          }
        }
      });
    });
  });
  