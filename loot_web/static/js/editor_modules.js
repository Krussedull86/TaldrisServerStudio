// Custom editors for Tabulator (editors.js)

let currentPopup = null;

function createPopupContainer(cell) {
    const cellRect = cell.getElement().getBoundingClientRect();
    const popupContainer = document.createElement("div");
    popupContainer.style.position = "absolute";
    popupContainer.style.top = `${window.scrollY + cellRect.bottom}px`;
    popupContainer.style.left = `${window.scrollX + cellRect.left}px`;
    popupContainer.style.background = "#000";
    popupContainer.style.border = "1px solid #ccc";
    popupContainer.style.padding = "10px";
    popupContainer.style.zIndex = 1000;
    return popupContainer;
}

function createCheckboxes(options, selectedValues, popupContainer) {
    const allCheckboxLabel = document.createElement("label");
    allCheckboxLabel.style.display = "block";

    const allCheckbox = document.createElement("input");
    allCheckbox.type = "checkbox";
    allCheckbox.value = "All";
    allCheckbox.checked = selectedValues.length === options.length; // Check if all are selected

    allCheckboxLabel.appendChild(allCheckbox);
    allCheckboxLabel.appendChild(document.createTextNode("-Select All-"));
    popupContainer.appendChild(allCheckboxLabel);

    // Checkbox for each option
    options.forEach(option => {
        const checkboxLabel = document.createElement("label");
        checkboxLabel.style.display = "block";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = option;
        checkbox.checked = selectedValues.includes(option);

        checkboxLabel.appendChild(checkbox);
        checkboxLabel.appendChild(document.createTextNode(option));
        popupContainer.appendChild(checkboxLabel);
    });

    // Event listener to handle "All" checkbox behavior
    allCheckbox.addEventListener("change", () => {
        Array.from(popupContainer.querySelectorAll("input[type='checkbox']"))
            .forEach(cb => cb.checked = allCheckbox.checked);
    });
}

function cleanup(cell, popupContainer) {
    if (currentPopup) {
        document.body.removeChild(popupContainer);
        currentPopup = null;
    }
    cell.getElement().classList.remove("tabulator-editing");
}

export function checkboxPopupEditor(cell, onRendered, success, cancel, options) {
    if (currentPopup) {
        cleanup(cell, currentPopup);
    }

    cell.getElement().classList.add("tabulator-editing");
    const currentValue = cell.getValue();
    const selectedValues = currentValue ? currentValue.split(", ") : [];
    const popupContainer = createPopupContainer(cell);

    createCheckboxes(options, selectedValues, popupContainer);

    const saveButton = document.createElement("button");
    saveButton.textContent = "✔️";
    saveButton.onclick = () => {
        const selectedValues = Array.from(popupContainer.querySelectorAll("input[type='checkbox']:checked"))
            .map(cb => cb.value)
            .filter(value => value !== "All")  // Exclude "All" from saved values
            .join(", ");
        success(selectedValues);
        cleanup(cell, popupContainer);
    };

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "✖️";
    cancelButton.onclick = () => {
        cancel();
        cleanup(cell, popupContainer);
    };

    popupContainer.appendChild(saveButton);
    popupContainer.appendChild(cancelButton);
    document.body.appendChild(popupContainer);
    currentPopup = popupContainer;

    saveButton.focus();
    onRendered(() => cleanup(cell, popupContainer));

    document.addEventListener("mousedown", function closePopup(event) {
        const targetCell = event.target.closest(".tabulator-cell");
        if (currentPopup && !currentPopup.contains(event.target) && (!targetCell || targetCell !== cell.getElement())) {
            cleanup(cell, popupContainer);
            document.removeEventListener("mousedown", closePopup);
        }
    });

    popupContainer.addEventListener("keydown", function(event) {
        if (event.key === "Enter") {
            saveButton.click();
        }
    });

    popupContainer.setAttribute("tabindex", "0");
    popupContainer.focus();
}

export function zoneEditor(cell, onRendered, success, cancel) {
    const options = [
        "Tier1",
        "Tier2",
        "Tier3",
        "Tier4",
        "Tier5",
        "Tier6",
        "Tier7",
        "Tier8",
        "Tier9",
        "Unique"
    ];
    checkboxPopupEditor(cell, onRendered, success, cancel, options);
}

export function usageEditor(cell, onRendered, success, cancel) {
    const options = [
        "Coast",
        "ContaminatedArea",
        "Farm",
        "Firefighter",
        "Hunting",
        "Industrial",
        "Lunapark",
        "Medic",
        "Military",
        "Office",
        "Police",
        "Prison",
        "School",
        "SeasonalEvent",
        "Special",
        "Town",
        "Underground",
        "Village"
    ];
    checkboxPopupEditor(cell, onRendered, success, cancel, options);
}

export function tagEditor(cell, onRendered, success, cancel) {
    const options = [
        "shelves",
        "floor",
        "ground"
    ];
    checkboxPopupEditor(cell, onRendered, success, cancel, options);
}






let dzsa_currentPopup = null;

function dzsa_createPopup(inputElement) {
    const rect = inputElement.getBoundingClientRect();
    const popup = document.createElement("div");

    Object.assign(popup.style, {
        position: "absolute",
        top: `${window.scrollY + rect.bottom + 10}px`,
        left: `${window.scrollX + rect.left}px`,
        background: "#000",
        border: "1px solid #ccc",
        padding: "10px",
        zIndex: 1000,
        maxWidth: "max-content", // Only as wide as needed to fit content
        whiteSpace: "nowrap",     // Prevent text wrapping within the popup
    });

    return popup;
}

function dzsa_createOptions(options, selectedValues, popup, allowMultiple) {
    const createOption = (option, isSelected) => {
        const input = document.createElement("input");
        input.type = allowMultiple ? "checkbox" : "radio";
        input.value = option.option;
        input.checked = isSelected;
        if (!allowMultiple) input.name = "dzsa_radioGroup";  // Ensure only one radio button can be selected
        input.style.marginRight = "8px"; // Add space between the checkbox/radio button and the text
        return input;
    };

    if (allowMultiple) {
        // Create the "Select All" checkbox only when multiple selections are allowed
        const selectAllLabel = document.createElement("label");
        selectAllLabel.style.display = "block";  // Each option on a new line

        const selectAll = document.createElement("input");
        selectAll.type = "checkbox";
        selectAll.dataset.selectAll = "true"; // Unique identifier for "Select All"
        selectAll.checked = selectedValues.length === options.length;
        selectAll.addEventListener("change", () => {
            popup.querySelectorAll("input[type='checkbox']").forEach(cb => cb.checked = selectAll.checked);
        });

        selectAllLabel.appendChild(selectAll);
        selectAllLabel.appendChild(document.createTextNode(" - Select All - "));
        popup.appendChild(selectAllLabel);

        options.forEach(option => {
            const label = document.createElement("label");
            label.style.display = "block";
            label.appendChild(createOption(option, selectedValues.includes(option.option)));
            label.appendChild(document.createTextNode(" " + option.alias));
            popup.appendChild(label);
        });
    } else {
        options.forEach(option => {
            const label = document.createElement("label");
            label.style.display = "block";
            label.appendChild(createOption(option, selectedValues.includes(option.option)));
            label.appendChild(document.createTextNode(" " + option.alias));
            popup.appendChild(label);
        });
    }
}

function dzsa_cleanup(popup) {
    if (dzsa_currentPopup) {
        document.body.removeChild(popup);
        dzsa_currentPopup = null;
    }
}

export function dzsa_openCheckboxPopup(inputElement, options, selectedValues = [], allowMultiple = true) {
    if (dzsa_currentPopup) dzsa_cleanup(dzsa_currentPopup);

    const popup = dzsa_createPopup(inputElement);
    dzsa_createOptions(options, selectedValues, popup, allowMultiple);

    const saveButton = document.createElement("button");
    saveButton.textContent = "✔️";
    saveButton.onclick = () => {
        const selected = Array.from(popup.querySelectorAll("input:checked"))
            .filter(input => !input.dataset.selectAll) // Exclude "Select All" based on data attribute
            .map(input => input.value);
        inputElement.value = selected.join(", ");
        dzsa_cleanup(popup);
    };

    const cancelButton = document.createElement("button");
    cancelButton.textContent = "✖️";
    cancelButton.onclick = () => dzsa_cleanup(popup);

    popup.appendChild(saveButton);
    popup.appendChild(cancelButton);
    document.body.appendChild(popup);
    dzsa_currentPopup = popup;

    saveButton.focus();

    document.addEventListener("mousedown", function closeOnClickOutside(event) {
        if (!popup.contains(event.target) && event.target !== inputElement) {
            dzsa_cleanup(popup);
            document.removeEventListener("mousedown", closeOnClickOutside);
        }
    });

    popup.setAttribute("tabindex", "0");
    popup.focus();
}
