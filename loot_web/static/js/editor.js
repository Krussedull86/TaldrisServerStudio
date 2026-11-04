window.initEditorJS = async function() {

    let tableReady = false

    const tutorialModal = document.getElementById('tutorialModal');
    let tutModalObj = new bootstrap.Modal(tutorialModal, {});

    // When page is fully loaded
    queueMicrotask(function () {
        getFileName();
        tutorialStatus('backend/tutorial.php');
    });

    function tutorialStatus(url) {
        fetch(url)
        .then(response => response.json())  // Parse the response as JSON
        .then(data => {
            if (data.status === 'yes') {  // Check the 'status' value in the JSON response
                tutModalObj.show();
            }
        })
        .catch(error => console.error('Error:', error));
    };

    // Import custom editors
    const customEditors = await import('./editor_modules.js')

    document.getElementById("btn_filterClear").addEventListener("click", function() { clearFilter(); });
    document.getElementById("btn_save").addEventListener("click", function() { saveProgress(table.getData()); });
    document.getElementById("btn_remove").addEventListener("click", function() { removeRow(); });

    document.getElementById("btn_min2max").addEventListener("click", function() { min2max(); });
    document.getElementById("btn_max2min").addEventListener("click", function() { max2min(); });

    document.getElementById("btn_dismissCookie").addEventListener("click", function() { tutorialStatus('backend/tutorial.php?dismiss=1'); });

    // Show tutorial modal

    document.getElementById("btn_test").addEventListener("click", function() {
        tutModalObj.show();
    });

    tutorialModal.addEventListener('shown.bs.modal', () => {
        const body = tutorialModal.querySelector('.modal-body');
        body.textContent = 'Open XML selects your types.xml. Double-click numeric cells to edit. Click a row to select it, Ctrl+click to add or remove individual rows, or Shift+click to select a range in the current filtered and sorted list. Select rows and enable columns in Bulk mode to change many items. Save changes stores a project revision on this PC. Undo and Redo move between saved revisions. Export XML writes your edited XML using a Windows file dialog. Export writes a separate XML file. Save to mission uses the Server Studio guarded writer and keeps a backup. Autosave stores a project revision every minute. Saved files lets you reopen projects and export earlier revisions. Tier maps displays the bundled map references.';
    });

    // Undo button
    let btnUndo = document.getElementById("btn_undo");
    btnUndo.addEventListener("click", function(){
        OhShitFunction('undo');
        coolDown(btnUndo);
    });
    
    // Redo button
    let btnRedo = document.getElementById("btn_redo");
    btnRedo.addEventListener("click", function(){
        OhShitFunction('redo');
        coolDown(btnRedo);
    });

    // Download button
    document.getElementById("btn_download").addEventListener("click", function() {
        listFiles('?list&listAll');
        listFiles('?list&listVersions');
    });

    // CTRL + S (Save)
    document.addEventListener("keydown", function(event) {
        // Check if Ctrl (or Command on macOS) and S are pressed
        if ((event.ctrlKey || event.metaKey) && event.key === "s") {
            event.preventDefault(); // Prevent the default browser action
            saveProgress(table.getData()); // Call the save function
        }
    });

    // CTRL + Z (Undo)
    document.addEventListener("keydown", function(event) {
        // Check if Ctrl (or Command on macOS) and Z are pressed
        if ((event.ctrlKey || event.metaKey) && event.key === "z") {
            event.preventDefault(); // Prevent the default browser action
            OhShitFunction('undo'); // Call undo function
        }
    });

    let toggleSwitch = document.getElementById('bulkSwitch');

    let btnApply = document.getElementById("bulk_btn_applyBulkChange");
    btnApply.addEventListener("click", () => {
        applyBulk();
        coolDown(btnApply);
    });

    let btnApplyPercent = document.getElementById("bulk_btn_plusPercent");
    btnApplyPercent.addEventListener("click", () => {
        bulkUpdate(true, true)
        coolDown(btnApplyPercent);
    });

    let btnApplyFixed = document.getElementById("bulk_btn_plusValue");
    btnApplyFixed.addEventListener("click", () => {
        bulkUpdate(true, false)
        coolDown(btnApplyFixed);
    });

    function coolDown(btn) {
        // Disable the button
        btn.disabled = true;

        // Re-enable the button after the cooldown time
        setTimeout(() => {
            btn.disabled = false;
        }, 350);
    }


    // Global variable to store the count of checked checkboxes
    let checkedCount = 0;

    // Function to update the count of checked checkboxes, label text, and toggle classes
    function updateStates() {
        // List of checkbox IDs and corresponding suffix
        const checkboxIds = [
            "bulk_toggle_nominal",
            "bulk_toggle_lifetime",
            "bulk_toggle_restock",
            "bulk_toggle_min",
            "bulk_toggle_quantmin",
            "bulk_toggle_quantmax",
            "bulk_toggle_cost",
            "bulk_toggle_category",
            "bulk_toggle_tag",
            "bulk_toggle_usage",
            "bulk_toggle_value"
        ];

        // Count the number of checked checkboxes
        checkedCount = checkboxIds.reduce((count, id) => {
            const checkbox = document.getElementById(id);
            const suffix = id.split("_")[2]; // Extract suffix dynamically
            const label = document.getElementById(`bulk_toggle_label_${suffix}`);
            const divById = document.getElementById(suffix); // Div element with matching ID
            const divByAttribute = document.querySelector(`[tabulator-field="${suffix}"]`); // Div with custom attribute

            if (checkbox) {
                // Update label content based on checkbox state
                if (label) {
                    if (checkbox.disabled) {
                        label.innerHTML = "<span class='dz_disabledText'>Disabled</span>";
                    } else {
                        label.innerHTML = checkbox.checked
                            ? "<span class='dz_activeColumnLabel'>Active</span>"
                            : "<span class='dz_disabledText'>Inactive</span>";
                    }
                }

                // Add or remove class based on checkbox state
                const isActive = checkbox.checked && !checkbox.disabled;
                if (divById) {
                    divById.classList.toggle("dz_activeColumn", isActive);
                    divById.classList.toggle("dz_disabledColumn", checkbox.disabled);
                }
                if (divByAttribute) {
                    divByAttribute.classList.toggle("dz_activeColumn", isActive);
                    divByAttribute.classList.toggle("dz_disabledColumn", checkbox.disabled);
                }

                // Count checked checkboxes
                return checkbox.checked ? count + 1 : count;
            }

            return count;
        }, 0);

        // Handle dz_fixedAbsoluteDisabled for bulkSwitch
        const bulkSwitch = document.getElementById("bulkSwitch");
        const labels = [
            document.getElementById("label_nonEmpty"),
            document.getElementById("label_fixedValue"),
            document.getElementById("label_percentageValue")
        ];

        if (bulkSwitch) {
            labels.forEach(label => {
                if (label) {
                    // Add or remove class based on bulkSwitch state
                    label.classList.toggle("dz_fixedAbsoluteDisabled", !bulkSwitch.checked);
                }
            });
        }
    }

    // Add event listeners to update states (count, labels, and classes)
    function setupListeners() {
        const checkboxIds = [
            "bulk_toggle_nominal",
            "bulk_toggle_lifetime",
            "bulk_toggle_restock",
            "bulk_toggle_min",
            "bulk_toggle_quantmin",
            "bulk_toggle_quantmax",
            "bulk_toggle_cost",
            "bulk_toggle_category",
            "bulk_toggle_tag",
            "bulk_toggle_usage",
            "bulk_toggle_value",
            "bulkSwitch"
        ];

        // Attach listeners to each checkbox
        checkboxIds.forEach(id => {
            const checkbox = document.getElementById(id);
            if (checkbox) {
                // Listen for changes in checkbox state
                checkbox.addEventListener("change", updateStates);

                // Listen for changes in the disabled property
                const observer = new MutationObserver(updateStates);
                observer.observe(checkbox, { attributes: true, attributeFilter: ["disabled"] });
            }
        });

        // Initial state update
        updateStates();
    }

    // Initialize listeners
    setupListeners();

    //
    // OSF
    //
    // JavaScript function to send JSON data to backend
    async function OhShitFunction(action = '') {
        try {

            var url = 'backend/osf.php';

            if (action == 'undo') { url = 'backend/osf.php?OSF=1&undo=1'; }
            if (action == 'redo') { url = 'backend/osf.php?OSF=1&redo=1'; }

            const response = await fetch(url);
            if (!response.ok) throw new Error('HTTP error! status: ' + response.status);

            //const responseData = await response.json();
            const responseText = await response.text();
            const responseJSON = JSON.parse(responseText);

            if (responseJSON.error) {
                window.showToastError(responseJSON.error);
                return;
            }

            if (responseJSON.data && responseJSON.data.toLowerCase().includes('nominal')) {

                // Send data to table
                table.setData(responseJSON.data);
                getFileName();

                // Display user feedback
                window.showToastSave(responseJSON.addon);
                return;
            }

        } catch (error) {
            throw new Error(error);
        }
    }


    const optionsCat = [
        { alias: "- Empty -", option: "" },
        { alias: "Books", option: "books" },
        { alias: "Clothes", option: "clothes" },
        { alias: "Containers", option: "containers" },
        { alias: "Explosives", option: "explosives" },
        { alias: "Food", option: "food" },
        { alias: "Loot dispatch", option: "lootdispatch" },
        { alias: "Tools", option: "tools" },
        { alias: "Weapons", option: "weapons" }
    ];

    // Triggering the popup on click of the input field
    document.getElementById("bulk_input_category").addEventListener("click", function() {
        // Fetch the current value from the input field (if any)
        const currentValue = this.value;
        const selectedValues = currentValue ? currentValue.split(", ") : [];

        // Open the checkbox popup at the bottom of the input
        customEditors.dzsa_openCheckboxPopup(this, optionsCat, selectedValues, false);
    });

    const optionsTag = [
        { alias: "Floor", option: "floor" },
        { alias: "Ground", option: "ground" },
        { alias: "Shelves", option: "shelves" }
    ];

    // Triggering the popup on click of the input field
    document.getElementById("bulk_input_tag").addEventListener("click", function() {
        // Fetch the current value from the input field (if any)
        const currentValue = this.value;
        const selectedValues = currentValue ? currentValue.split(", ") : [];

        // Open the checkbox popup at the bottom of the input
        customEditors.dzsa_openCheckboxPopup(this, optionsTag, selectedValues, true);
    });

    const optionsUsage = [
        { alias: "Coast", option: "Coast" },
        { alias: "ContaminatedArea", option: "ContaminatedArea" },
        { alias: "Farm", option: "Farm" },
        { alias: "Firefighter", option: "Firefighter" },
        { alias: "Hunting", option: "Hunting" },
        { alias: "Industrial", option: "Industrial" },
        { alias: "Lunapark", option: "Lunapark" },
        { alias: "Medic", option: "Medic" },
        { alias: "Military", option: "Military" },
        { alias: "Office", option: "Office" },
        { alias: "Police", option: "Police" },
        { alias: "Prison", option: "Prison" },
        { alias: "School", option: "School" },
        { alias: "SeasonalEvent", option: "SeasonalEvent" },
        { alias: "Special", option: "Special" },
        { alias: "Town", option: "Town" },
        { alias: "Underground", option: "Underground" },
        { alias: "Village", option: "Village" }
    ];

    // Triggering the popup on click of the input field
    document.getElementById("bulk_input_usage").addEventListener("click", function() {
        // Fetch the current value from the input field (if any)
        const currentValue = this.value;
        const selectedValues = currentValue ? currentValue.split(", ") : [];

        // Open the checkbox popup at the bottom of the input
        customEditors.dzsa_openCheckboxPopup(this, optionsUsage, selectedValues, true);
    });

    const optionsZone = [
        { alias: "Tier1", option: "Tier1" },
        { alias: "Tier2", option: "Tier2" },
        { alias: "Tier3", option: "Tier3" },
        { alias: "Tier4", option: "Tier4" },
        { alias: "Tier5", option: "Tier5" },
        { alias: "Tier6", option: "Tier6" },
        { alias: "Tier7", option: "Tier7" },
        { alias: "Tier8", option: "Tier8" },
        { alias: "Tier9", option: "Tier9" },
        { alias: "Unique", option: "Unique" }
    ];

    // Triggering the popup on click of the input field
    document.getElementById("bulk_input_value").addEventListener("click", function() {
        // Fetch the current value from the input field (if any)
        const currentValue = this.value;
        const selectedValues = currentValue ? currentValue.split(", ") : [];

        // Open the checkbox popup at the bottom of the input
        customEditors.dzsa_openCheckboxPopup(this, optionsZone, selectedValues, true);
    });


    function setFileName(text) {
        document.getElementById("fileName").innerHTML = text;
    }
    
    async function getFileName() {
        try {
            const url = 'backend/getFileName.php?fileName=1'; // Add query parameters for action and id
            const response = await fetch(url);
            if (!response.ok) throw new Error('HTTP error! status: ' + response.status);
    
            // Convert response to text
            const data = await response.text();
        
            // Usage example:
            setFileName(data); // Pass the text data directly to setFileName
            
        } catch (error) {
            console.error("Error fetching data:", error);
        }
    }    


    //
    // Management Accordian
    //
    document.getElementById("dz_listAllFiles").addEventListener("click", function() {
        listFiles('?list&listAll');
    });

    document.getElementById("dz_listVersions").addEventListener("click", function() {
        listFiles('?list&listVersions');
    });

    async function listFiles(opt = "?list") {
        try {
            const url = 'backend/listFiles.php'+opt; // Add query parameters for action and id
            const response = await fetch(url);
            if (!response.ok) throw new Error('HTTP error! status: ' + response.status);

            // Convert response to JSON
            const data = await response.json();

            if (opt == "?list&listVersions") {
                // Call updateFileWindow and pass the data to populate the table
                listAllVersions(data);
                return;
            }

            if (opt == "?list&listAll") {
                // Call updateFileWindow and pass the data to populate the table
                updateAllFilesWindow(data);
                return;
            }

            if (opt == "?list") {
                // Call updateFileWindow and pass the data to populate the table
                updateFileWindow(data);
                return;
            }
            
        } catch (error) {
            console.error("Error fetching data:", error);
        }
    }

    function listAllVersions(data) {
        // Get the table body by ID
        const tableBody = document.getElementById('all_versions').getElementsByTagName('tbody')[0];
        
        // Clear any existing rows in the table
        tableBody.innerHTML = '';
        
        // Iterate over the data array and create a row for each item
        data.forEach(item => {
            // Create a new row
            const row = document.createElement('tr');

            const cellFileId = document.createElement('td');
            cellFileId.textContent = item.file_id;

            const cellFileTitle = document.createElement('td');
            cellFileTitle.textContent = item.file_title;

            const cellModifiedDate = document.createElement('td');
            cellModifiedDate.textContent = item.modified_date;

            const cellRevision = document.createElement('td');
            cellRevision.textContent = item.revision;

            // Create a <td> for buttons
            const cellButtons = document.createElement('td');

            const btnEdit = document.createElement('button');
            btnEdit.type = 'button';
            btnEdit.className = 'btn btn-primary dz_btn-xs';

            if (item.status == 'active') {
                // Create Active button
                btnEdit.textContent = 'Active';
                btnEdit.setAttribute('disabled', 'true');
            } else {
                // Create Edit button
                btnEdit.textContent = 'Load version';
                btnEdit.addEventListener('click', () => {
                    window.desktopFileAction('load', item);
                });
            }

            // Create Download button
            const btnDownload = document.createElement('button');
            btnDownload.type = 'button';
            btnDownload.className = 'btn btn-primary dz_btn-xs';
            btnDownload.textContent = 'Export XML';
            btnDownload.addEventListener('click', () => {
                window.desktopFileAction('export', item);
            });

            // Create Delete version button
            const btnDeleteVersion = document.createElement('button');
            btnDeleteVersion.type = 'button';
            btnDeleteVersion.className = 'btn btn-primary dz_btn-xs-error';
            btnDeleteVersion.textContent = 'Delete version';
            btnDeleteVersion.addEventListener('click', () => {
                window.desktopFileAction('deleteRevision', item);
            });

            // Append cells to the row
            row.appendChild(cellFileId);
            row.appendChild(cellFileTitle);
            row.appendChild(cellModifiedDate);
            row.appendChild(cellRevision);
            row.appendChild(cellButtons);

            // Append buttons with spaces
            cellButtons.appendChild(btnEdit);
            cellButtons.appendChild(document.createTextNode(' ')); // Add space
            cellButtons.appendChild(btnDownload);
            cellButtons.appendChild(document.createTextNode(' ')); // Add space
            cellButtons.appendChild(btnDeleteVersion);

            // Append the row to the table body
            tableBody.appendChild(row);
        });
    }

    function updateAllFilesWindow(data) {
        // Get the table body by ID
        const tableBody = document.getElementById('all_files').getElementsByTagName('tbody')[0];
        
        // Clear any existing rows in the table
        tableBody.innerHTML = '';
        
        // Iterate over the data array and create a row for each item
        data.forEach(item => {
            // Create a new row
            const row = document.createElement('tr');

            const cellFileId = document.createElement('td');
            cellFileId.textContent = item.file_id;

            const cellFileTitle = document.createElement('td');
            cellFileTitle.textContent = item.file_title;

            const cellModifiedDate = document.createElement('td');
            cellModifiedDate.textContent = item.modified_date;

            const cellRevision = document.createElement('td');
            cellRevision.textContent = item.revision;

            // Create a <td> for buttons
            const cellButtons = document.createElement('td');

            const btnEdit = document.createElement('button');
            btnEdit.type = 'button';
            btnEdit.className = 'btn btn-primary dz_btn-xs';

            if (item.status == 'active') {
                // Create Active button
                btnEdit.textContent = 'Active';
                btnEdit.setAttribute('disabled', 'true');
            } else {
                // Create Edit button
                btnEdit.textContent = 'Load file';
                btnEdit.addEventListener('click', () => {
                    window.desktopFileAction('load', item);
                });
            }

            // Create Download button
            const btnDownload = document.createElement('button');
            btnDownload.type = 'button';
            btnDownload.className = 'btn btn-primary dz_btn-xs';
            btnDownload.textContent = 'Export XML';
            btnDownload.addEventListener('click', () => {
                window.desktopFileAction('export', item);
            });

            // Create Delete file button
            const btnDeleteFile = document.createElement('button');
            btnDeleteFile.type = 'button';
            btnDeleteFile.className = 'btn btn-primary dz_btn-xs-error';
            btnDeleteFile.textContent = 'Delete file';
            btnDeleteFile.addEventListener('click', () => {
                window.desktopFileAction('delete', item);
            });

            // Append cells to the row
            row.appendChild(cellFileId);
            row.appendChild(cellFileTitle);
            row.appendChild(cellModifiedDate);
            row.appendChild(cellRevision);
            row.appendChild(cellButtons);

            // Append buttons with spaces
            cellButtons.appendChild(btnEdit);
            cellButtons.appendChild(document.createTextNode(' ')); // Add space
            cellButtons.appendChild(btnDownload);
            cellButtons.appendChild(document.createTextNode(' ')); // Add space
            cellButtons.appendChild(btnDeleteFile);

            // Append the row to the table body
            tableBody.appendChild(row);
        });
    }

    function updateFileWindow(data) {
        // Get the table body by ID
        const tableBody = document.getElementById('files_table').getElementsByTagName('tbody')[0];
    
        // Clear any existing rows in the table
        tableBody.innerHTML = '';
    
        // Iterate over the data array and create a row for each item
        data.forEach(item => {
            // Create a new row
            const row = document.createElement('tr');
    
            const cellFileId = document.createElement('td');
            cellFileId.textContent = item.file_id;
    
            const cellFileTitle = document.createElement('td');
            cellFileTitle.textContent = item.file_title;

            const cellModifiedDate = document.createElement('td');
            cellModifiedDate.textContent = item.modified_date;

            const cellRevision = document.createElement('td');
            cellRevision.textContent = item.revision;
    
            const cellXmlDownload = document.createElement('td');
            cellXmlDownload.textContent = item.xml_downloaded;
    
            // Create a <td> for links and add an <a> element within it
            const cellLinks = document.createElement('td');
            const link = document.createElement('a');
            link.href = item.linkDL; // Set the href to item.links
            link.textContent = "Download"; // Set the text of the link
            link.target = "_blank"; // Optional: opens link in a new tab
            cellLinks.appendChild(link); // Append the <a> to the <td>
    
            // Append cells to the row
            row.appendChild(cellFileId);
            row.appendChild(cellFileTitle);
            row.appendChild(cellModifiedDate);
            row.appendChild(cellRevision);
            row.appendChild(cellXmlDownload);
            row.appendChild(cellLinks);
    
            // Append the row to the table body
            tableBody.appendChild(row);
        });
    
    }

    // Function to clear table header filters
    function clearFilter() {
        table.clearHeaderFilter();
        window.showToastTools("Cleared all filters"); // Display feedback message
    }

    // Function to remove selected/active rows
    function removeRow() {

        // Fetch selected data from Tabulator
        const selectedData = table.getSelectedData();

        if (selectedData.length > 0) {
            
            // Get data
            const rows = selectedData;

            // Extract the name from each row and store it in an array
            const rowNames = rows.map(row => row.name);

            // Temporarily disable table redraw to improve performance during batch update
            table.blockRedraw();

            // Delete each selected/active row based on its name
            rowNames.forEach(name => {
                table.deleteRow(name);
            });

            // Re-enable table redraw to reflect changes
            table.restoreRedraw();

            let msg = "Removed.. something.."
            if (rows.length > 1) {
                msg = "Removed " + rows.length + " rows"
            } else {
                msg = "Removed " + rows.length + " row"
            }
            
            window.showToastTools(msg);

            // Save after deletion
            saveProgress(table.getData(), '', true);
            updateApplyButton();

        } else {
            window.showToastError('No rows selected.');
        }
    }

    //
    // Autosave feature
    //
    let autoSaveInterval = null;  // Variable to store the interval ID

    // Function to start the auto-save feature
    function startAutoSave() {
        autoSaveInterval = setInterval(() => {
            saveProgress(table.getData(), "Autosave:"); // Call saveProgress with table data
            getFileName();
        }, 60000);  // 1 minutes in milliseconds
        console.info("Autosave: Enabled");
        window.showToastTools("Autosave: Enabled");  // Display feedback message
    }

    // Function to stop the Autosave: feature
    function stopAutoSave() {
        clearInterval(autoSaveInterval);  // Clear the interval
        console.info("Autosave: Disabled");
        window.showToastTools("Autosave: Disabled");
    }

    // Event listener for the toggle switch
    document.getElementById('flexSwitchCheckDefault').addEventListener('change', (event) => {
        if (event.target.checked) {
            startAutoSave();
            localStorage.setItem('dz_autoSaveEnabled', 'true');  // Save state to localStorage
        } else {
            stopAutoSave();
            localStorage.setItem('dz_autoSaveEnabled', 'false');  // Save state to localStorage
        }
    });

    // Check localStorage on page load to set the toggle switch and auto-save state
    queueMicrotask(() => {
        const toggleSwitch = document.getElementById('flexSwitchCheckDefault');
        
        // Check if localStorage has a saved state for autoSaveEnabled
        const savedState = localStorage.getItem('dz_autoSaveEnabled');

        if (savedState === null) {
            // If no localStorage value, use the HTML default checked state of the toggle switch
            const isAutoSaveEnabled = toggleSwitch.checked;
            localStorage.setItem('dz_autoSaveEnabled', isAutoSaveEnabled ? 'true' : 'false');

            // Start auto-save if the switch is checked by default
            if (isAutoSaveEnabled) {
                startAutoSave();
            }
        } else {
            // If localStorage has a saved state, apply it to the toggle switch
            const isAutoSaveEnabled = savedState === 'true';
            toggleSwitch.checked = isAutoSaveEnabled;

            // Start auto-save if it was enabled previously
            if (isAutoSaveEnabled) {
                startAutoSave();
            }
        }
    });



    //
    // Save progress
    //
    // JavaScript function to send JSON data to backend
    async function saveProgress(data, message = "", silent = false) {

        const url = 'backend/save.php';

        try {
            const response = await fetch(url, {
                method: "POST",
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)  // Convert data to JSON string
            });

            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);

            const responseText = await response.text();
            const responseJSON = JSON.parse(responseText);

            var rMessage;

            // Backend either saved or was already up-to-date
            if (responseText.includes('Saved') || responseText.includes('up-to-date')) {

                if (message !== "") {
                    rMessage = message.concat(" ", responseJSON.data);
                } else {
                    rMessage = responseJSON.data;
                }
                getFileName();
            } else {
                rMessage = responseJSON.error;
                throw new Error("Save failed: " + responseJSON.error); // If response text indicates failure
            }

        } catch (error) {
            rMessage = error.message;
            console.error("Error:", rMessage)
        }

        if (!silent) {
            // Display user feedback
            window.showToastSave(rMessage);
        }
    }


    function applyBulk() {
        // Fetch selected data from Tabulator
        const selectedData = table.getSelectedData();

        if (selectedData.length > 0) {
            if (checkedCount > 0) {
                // Get data
                const rows = selectedData;
            
                // Check if non-empty-only mode is enabled
                const applyToNonEmptyOnly = document.getElementById("bulk_toggle_nonEmpty").checked;
            
                // Fields that require a numeric value and should never be empty
                const requiredNumericFields = ["nominal", "lifetime", "restock", "min", "quantmin", "quantmax"];
            
                // Initialize the count for updated rows
                let updatedCount = 0;
            
                // Generate an array of updated rows based on the specified operation
                const updatedRows = rows.map((row) => {
                    // Get the values from the corresponding input fields
                    const getInputValue = (inputId, field) => {
                        const input = document.getElementById(inputId);
                        
                        // Check if the input exists and is not disabled
                        if (input && !input.disabled) {
                            const inputValue = input.value;
            
                            // Check for required numeric fields
                            if (requiredNumericFields.includes(field)) {
                                const numericValue = parseFloat(inputValue);
            
                                // Skip update if the input is empty or not a valid number
                                if (isNaN(numericValue) || inputValue === "") {
                                    return row[field];
                                }
            
                                // Apply the value only if bulk_nonEmpty is off, or if it's on and the cell is non-zero/non-empty
                                if (!applyToNonEmptyOnly || (applyToNonEmptyOnly && row[field] !== "" && row[field] !== 0)) {
                                    return numericValue;
                                }
            
                                return row[field]; // Return current cell value if conditions are not met
                            }
            
                            // For other fields, apply the value based on the bulk_nonEmpty toggle
                            if (!applyToNonEmptyOnly || (applyToNonEmptyOnly && row[field] !== "" && row[field] !== 0)) {
                                return inputValue;
                            }
                        }
            
                        // Return the current value from the row if input is disabled or the cell is empty
                        return row[field];
                    };
            
                    // Prepare the updated row with values from corresponding inputs if valid
                    const updatedRow = {
                        name: row.name,
                        nominal: getInputValue('bulk_input_nominal', 'nominal'),
                        lifetime: getInputValue('bulk_input_lifetime', 'lifetime'),
                        restock: getInputValue('bulk_input_restock', 'restock'),
                        min: getInputValue('bulk_input_min', 'min'),
                        quantmin: getInputValue('bulk_input_quantmin', 'quantmin'),
                        quantmax: getInputValue('bulk_input_quantmax', 'quantmax'),
                        cost: getInputValue('bulk_input_cost', 'cost'),
                        category: getInputValue('bulk_input_category', 'category'),
                        tag: getInputValue('bulk_input_tag', 'tag'),
                        usage: getInputValue('bulk_input_usage', 'usage'),
                        value: getInputValue('bulk_input_value', 'value'),
                    };
            
                    // Compare if the row is updated by checking if the original value differs from the updated value
                    let rowChanged = false;
                    Object.keys(updatedRow).forEach((field) => {
                        if (updatedRow[field] !== row[field]) {
                            rowChanged = true;  // Mark this row as changed if any field has been updated
                        }
                    });
            
                    // Increment count if the row was actually updated
                    if (rowChanged) {
                        updatedCount++;
                    }
            
                    return updatedRow;
                });
            
                // Update table with modified rows
                table.blockRedraw();  // Temporarily disable table redraw to improve performance during batch update
                table.updateData(updatedRows);
                table.restoreRedraw();  // Re-enable table redraw to reflect changes

                // Save after bulk change
                saveProgress(table.getData(), '', true);
                
                // Show toast message with the number of updated rows
                window.showToastTools(`${updatedCount} row(s) updated`);
            } else {
                window.showToastError('No columns activated');
            }
        } else {
            window.showToastError('No rows selected');
        }
    }
    
    function min2max() {
        // Fetch selected data from Tabulator
        const selectedData = table.getSelectedData();
    
        if (selectedData.length > 0) {
            // Prepare an array of updated rows and count how many were changed
            let updatedCount = 0;
            const updatedRows = selectedData.map((row) => {
                // Check if the 'min' value exists and is numeric
                const minValue = parseFloat(row.min);
                if (!isNaN(minValue)) {
                    // Create a copy of the row and update the 'nominal' field
                    let newRow = { ...row };
                    if (newRow.nominal !== minValue) {
                        newRow.nominal = minValue;
                        updatedCount++; // Increment count for changed rows
                    }
                    return newRow;
                }
                return row; // Return unchanged row if 'min' is invalid
            });
    
            // Update the table with modified rows
            table.blockRedraw();
            table.updateData(updatedRows);
            table.restoreRedraw();
    
            // Save after change
            saveProgress(table.getData(), '', true);

            // Display a success message
            window.showToastTools(`${updatedCount} row(s) updated`);
        } else {
            // Display an error message if no rows are selected
            window.showToastError('No rows selected');
        }
    }

    function max2min() {
        // Fetch selected data from Tabulator
        const selectedData = table.getSelectedData();
    
        if (selectedData.length > 0) {
            // Prepare an array of updated rows and count how many were changed
            let updatedCount = 0;
            const updatedRows = selectedData.map((row) => {
                // Check if the 'nominal' value exists and is numeric
                const nominalValue = parseFloat(row.nominal);
                if (!isNaN(nominalValue)) {
                    // Create a copy of the row and update the 'min' field
                    let newRow = { ...row };
                    if (newRow.min !== nominalValue) {
                        newRow.min = nominalValue;
                        updatedCount++; // Increment count for changed rows
                    }
                    return newRow;
                }
                return row; // Return unchanged row if 'nominal' is invalid
            });
    
            // Update the table with modified rows
            table.blockRedraw();
            table.updateData(updatedRows);
            table.restoreRedraw();
    
            // Save after change
            saveProgress(table.getData(), '', true);

            // Display a success message
            window.showToastTools(`${updatedCount} row(s) updated`);
        } else {
            // Display an error message if no rows are selected
            window.showToastError('No rows selected');
        }
    }
    

    function bulkUpdate(isIncrease, isPercentage = true) {

        // Fetch selected data from Tabulator
        const selectedData = table.getSelectedData();

        if (selectedData.length > 0) {
            if (checkedCount > 0) {
                // Get data
                const rows = selectedData;

                // Get the percentage or number value from the corresponding input field
                const inputId = isPercentage ? "bulk_btn_percent" : "bulk_btn_value";
                const inputValue = parseFloat(document.getElementById(inputId).value) || 0;
            
                // Calculate the multiplier or adjustment value based on the selected mode
                const adjustment = isPercentage
                    ? (isIncrease ? (1 + inputValue / 100) : (1 - inputValue / 100))
                    : (isIncrease ? inputValue : -inputValue); // For absolute change, adjust based on isIncrease
            
                // Define individual limits for each field
                const limits = {
                    nominal: { min: 0, max: 1000 },
                    lifetime: { min: 0, max: 4999980 },
                    restock: { min: 0, max: 4999980 },
                    min: { min: 0, max: 1000 },
                    quantmin: { min: 0, max: 100 },
                    quantmax: { min: 0, max: 100 },
                    cost: { min: 0, max: 1000 },
                };
            
                // Helper function to apply field-specific limits
                const applyLimits = (value, field) => {
                    const { min, max } = limits[field];
                    return Math.round(Math.max(min, Math.min(value, max)));
                };
            
                // Check if non-empty-only mode is enabled
                const applyToNonEmptyOnly = document.getElementById("bulk_toggle_nonEmpty").checked;
            
                // Prepare an array of updated rows and count how many were changed
                let updatedCount = 0;
                const updatedRows = rows.map((row) => {
                    let newRow = { ...row };
                    let rowChanged = false; // Track if this row is modified
            
                    // Define fields that will be updated based on their corresponding toggle checkbox
                    const fields = Object.keys(limits);
            
                    fields.forEach(field => {
                        const toggle = document.getElementById(`bulk_toggle_${field}`);
                        if (toggle && toggle.checked) {
                            const originalValue = row[field];
                            
                            // Ensure the original value is treated as a number
                            const numericOriginalValue = parseFloat(originalValue);
            
                            // Skip if non-empty mode is enabled and the value is empty or zero
                            if (applyToNonEmptyOnly && (isNaN(numericOriginalValue) || numericOriginalValue === 0)) return;
            
                            if (!isNaN(numericOriginalValue)) {
                                // Calculate new value (multiply for percentage, add for absolute change)
                                const newValue = isPercentage
                                    ? applyLimits(numericOriginalValue * adjustment, field) // Multiplicative for percentage
                                    : applyLimits(numericOriginalValue + adjustment, field); // Additive for absolute change
            
                                // If the value changes, update the row and mark it as changed
                                if (newValue !== numericOriginalValue) {
                                    newRow[field] = newValue;
                                    rowChanged = true; // Mark row as changed
                                }
                            }
                        }
                    });
            
                    if (rowChanged) updatedCount++; // Increment count if row was changed
                    return newRow;
                });
            
                // Update table with modified rows
                table.blockRedraw();
                table.updateData(updatedRows);
                table.restoreRedraw();
                window.showToastTools(`${updatedCount} row(s) updated`);

                // Save after bulk change
                saveProgress(table.getData(), '', true);
            } else {
                window.showToastError('No columns activated');
            }
        } else {
            window.showToastError('No rows selected');
        }
    }
    
    

    // Initialize Tabulator
    var table = new Tabulator("#tabulator-table", {

        data: jsonDataMod,

        index: "name", //set the index field to the "name" field.
        layout: "fitDataFill",
        initialSort: [{column:"name", dir:"asc"}],

        keybindings: false, //disable all key bindings
        minHeight: 300, //do not let table get smaller than 300 px heigh
        maxHeight: "100%", //do not let table get bigger than the height of its parent element
        addRowPos: "top", // when adding a new row, add it to the top of the table
        validationMode: "blocking", //highlight cells with validation errors but don't stop the edit
        resizableColumnGuide: true,

        history: true,
        persistenceID: "perststance-dzsatools",
        persistence: {sort: true, filter: true, columns: true },
        persistenceMode: "local",

        selectableRows: true,
        selectableRowsRangeMode: "click", // Ctrl/Meta toggles; Shift selects displayed row ranges.
        selectableRowsPersistence: true,

        rowHeader: {
            formatter: "rowSelection",
            titleFormatter: "rowSelection",
            titleFormatterParams: {
                rowRange: "active"
            },
            headerSort: false,
            resizable: false,
            frozen: true,
            headerHozAlign: "center",
            hozAlign: "center",
            width: 42
        },

        columns: [

            // Name
            {
                title: "Name <span class='subheader'>*Not editable</span>  <i class='fa-solid fa-circle-question'></i>",
                field: "name",
                minWidth: "230px",
                sorter:"string",
                headerTooltip:"Classname of the item",
                headerFilter:"input",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{autocomplete:true,},
            },

            // Nominal
            {
                title: "Nominal  <i class='fa-solid fa-circle-question'></i>",
                field: "nominal",
                minWidth: "120px",
                headerTooltip:"Determines the maximum number of an item on the whole server",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:0,
                    max:1000,
                },
                sorter: "number",
                validator:["required", "min:0", "max:1000"],
                editor:"number",
                editorParams:{
                    min:0,
                    max:1000,
                    elementAttributes:{maxlength:"3"}
                }
            },

            // Lifetime
            {
                title: "Lifetime (sec)  <i class='fa-solid fa-circle-question'></i>",
                field: "lifetime",
                headerTooltip:"Time in seconds before an item despawns if it has not been touched",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:0,
                    max:4999980,
                },
                sorter: "number",
                editor:"number",
                validator:["required", "min:0", "max:4999980"],
                editorParams:{
                    min:0,
                    max:4999980,
                    elementAttributes:{maxlength:"7"}
                }
            },

            // Restock
            {
                title: "Restock (sec)  <i class='fa-solid fa-circle-question'></i>",
                field: "restock",
                headerTooltip:"Time in seconds for an item of the specified type to respawn. If the value is 0, all items will be spawned at once",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:0,
                    max:4999980,
                },
                sorter: "number",
                editor:"number",
                validator:["required", "min:0", "max:4999980"],
                editorParams:{
                    min:0,
                    max:4999980,
                    elementAttributes:{maxlength:"7"}
                }
            },

            // Min(imum)
            {
                title: "Min  <i class='fa-solid fa-circle-question'></i>",
                field: "min",
                minWidth: "120px",
                headerTooltip:"If the number of items in the world falls below this value, new items will be spawned",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:0,
                    max:1000,
                },
                sorter: "number", 
                validator:["required", "min:0", "max:1000"],
                editor:"number",
                editorParams:{
                    min:0,
                    max:1000,
                    elementAttributes:{maxlength:"3"}
                }
            },

            // Quantmin
            {
                title: "QuantMin  <i class='fa-solid fa-circle-question'></i>",
                field: "quantmin",
                headerTooltip:"Min % of the quantity, for example, for ammunition (number of bullets in a magazine. 100 = magazine is full)",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:-1,
                    max:100,
                },
                sorter: "number",
                validator:["required", "min:-1", "max:100"],
                editor:"number",
                editorParams:{
                    min:-1,
                    max:100,
                    elementAttributes:{maxlength:"3"}
                }
            },

            // Quantmax
            {
                title: "QuantMax  <i class='fa-solid fa-circle-question'></i>",
                field: "quantmax",
                headerTooltip:"Max % of the quantity, for example, for ammunition (number of bullets in a magazine. 100 = magazine is full)",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:-1,
                    max:100,
                },
                sorter: "number",
                validator:["required", "min:-1", "max:100"],
                editor:"number",
                editorParams:{
                    min:-1,
                    max:100,
                    elementAttributes:{maxlength:"3"}
                }
            },

            // Cost
            {
                title: "Cost  <i class='fa-solid fa-circle-question'></i>",
                field: "cost",
                minWidth: "120px",
                headerTooltip:"Priority for central economy (CE), the higher the value, the higher the priority",
                headerFilter:"number",
                headerFilterPlaceholder:"Filter...",
                headerFilterParams:{
                    min:0,
                    max:1000,
                },
                sorter: "number",
                validator:["required", "min:0", "max:1000"],
                editor:"number",
                editorParams:{
                    min:0,
                    max:1000,
                    elementAttributes:{maxlength:"3"}
                }
            },

            // Category
            {
                title: "Category  <i class='fa-solid fa-circle-question'></i>",
                field: "category",
                headerTooltip:"Determines the category of the item",
                headerFilter:"input",
                headerFilterPlaceholder:"Filter...",
                editor:"list",
                editorParams:{
                    autocomplete:true,
                    allowEmpty:true,
                    listOnEmpty:true,
                    values:{
                        "":"- Empty cell - ",
                        "books":"books",
                        "clothes":"clothes",
                        "containers":"containers",
                        "explosives":"explosives",
                        "food":"food",
                        "lootdispatch":"lootdispatch",
                        "tools":"tools",
                        "weapons":"weapons"
                    }}
            },

            // Tags
            {
                title: "Tags  <i class='fa-solid fa-circle-question'></i>",
                field: "tag",
                minWidth: "120px",
                headerTooltip:"Determines where the item is spawned depending on the group",
                headerFilter:"input",
                headerFilterPlaceholder:"Filter...",
                editor: customEditors.tagEditor
            },

            // Usage
            {
                title: "Usage  <i class='fa-solid fa-circle-question'></i>",
                field: "usage",
                headerTooltip:"Determines the group in which the item is spawned",
                headerFilter:"input",
                headerFilterPlaceholder:"Filter...",
                editor: customEditors.usageEditor
            },

            // Zone
            {
                title: "Zone  <i class='fa-solid fa-circle-question'></i>",
                field: "value",
                headerTooltip:"Determines the zone on the map where the item is spawned",
                headerFilter:"input",
                headerFilterPlaceholder:"Filter...",
                editor: customEditors.zoneEditor
            },
        ]
    });





    function throttle(mainFunction, delay) {
        let timerFlag = null; // Variable to keep track of the timer

        // Returning a throttled version 
        return (...args) => {
            if (timerFlag === null) { // If there is no timer currently running
            mainFunction(...args); // Execute the main function 
            timerFlag = setTimeout(() => { // Set a timer to clear the timerFlag after the specified delay
                timerFlag = null; // Clear the timerFlag to allow the main function to be executed again
            }, delay);
            }
        };
    }

    window.saveToHistory = () => {}; // Native project revisions are persisted on disk.

    table.on("tableBuilt", function(){
        console.log("TABLE READY");
        tableReady = true;
        const bulkScroll = document.getElementById('bulk-columns-scroll');
        const tableScroll = document.querySelector('.tabulator-tableholder');
        if (bulkScroll && tableScroll) {
            let syncing = false;
            const sync = (from, to) => { if (syncing) return; syncing = true; to.scrollLeft = from.scrollLeft; requestAnimationFrame(() => { syncing = false; }); };
            bulkScroll.addEventListener('scroll', () => sync(bulkScroll, tableScroll));
            tableScroll.addEventListener('scroll', () => sync(tableScroll, bulkScroll));
        }
    });

    // Add the event listener after table initialization
    table.on("cellEdited", function() {
        window.desktopDirty();
        window.saveToHistory()
    });

    // Check updated row
    table.on("rowUpdated", function() {
        window.desktopDirty();
        window.saveToHistory()
    });

    // Check updated row
    table.on("rowDeleted", function() {
        window.desktopDirty();
        window.saveToHistory()
    });

    // Update column width
    table.on("columnWidth", function({ _column }){
        applyWidthToTarget(_column.width, _column.definition.field);
     });

    // Update column width
    table.on("columnResized", function({_column}){
        applyWidthToTarget(_column.width, _column.definition.field);
    });

    table.on("rowSelectionChanged", function(data, rows, selected, deselected){
        if (tableReady) {
            updateApplyButton();
        };
    });

    function updateApplyButton() {
        if (table.getSelectedData().length > 0) {
            if (toggleSwitch.checked) {
                btnApply.disabled = false;
            }
        } else {
            btnApply.disabled = true;
        }
    }

    function applyWidthToTarget(width, targetId) {
        // Find the target div by its ID
        const targetDiv = document.getElementById(targetId);
      
        // Ensure the target div exists before proceeding
        if (targetDiv) {
          // Set the width of the target div to match the provided width
          targetDiv.style.width = `${width}px`;
        }
    }

    function setupToggleListeners() {
        // Select all checkboxes with IDs starting with "bulk_toggle"
        const checkboxes = document.querySelectorAll('input[id^="bulk_toggle"][type="checkbox"]');
    
        checkboxes.forEach((checkbox) => {
            // Add a change event listener to each checkbox
            checkbox.addEventListener("change", () => {
                const suffix = checkbox.id.replace("bulk_toggle_", ""); // Extract the suffix (e.g., "nominal")
                const input = document.getElementById(`bulk_input_${suffix}`); // Find the corresponding input
                if (input) {
                    input.disabled = !checkbox.checked;
                }
            });
        });
    }
    
    function toggleElements(enable) {
        // Select all elements with IDs starting with "bulk_"
        const bulkElements = document.querySelectorAll('[id^="bulk_"]');
    
        bulkElements.forEach((element) => {
            // Ensure the button with id "bulk_btn_applyBulkChange" is always disabled
            if (element.id === "bulk_btn_applyBulkChange") {
                element.disabled = true;
                return; // Skip further processing for this button
            }
    
            // Skip elements starting with "bulk_input" when enabling
            if (enable && element.id.startsWith("bulk_input")) return;
    
            // Enable or disable the element based on the checkbox state
            element.disabled = !enable;
    
            // If disabling, handle special cases
            if (!enable) {
                if (element.id.startsWith("bulk_toggle_") && element.type === "checkbox") {
                    element.checked = false;  // Uncheck any toggle checkboxes
                }
                if (element.id.startsWith("bulk_input") && element.tagName === "INPUT") {
                    element.value = "";  // Clear the value of any input elements
                }
            }
            if (tableReady) {
                updateApplyButton();
            }
        });
    }
    
    function toggleTabulatorClass(state) {
        const tabulatorTable = document.getElementById('bulkContainer');
        if (tabulatorTable) {
            tabulatorTable.classList.toggle('bulkmode-active', state);
            tabulatorTable.classList.toggle('bulkmode-inactive', !state);
        }
    
        toggleElements(state); // Enable/disable elements based on the state
        window.showToastTools(state ? "Bulk mode: Enabled" : "Bulk mode: Disabled");
    }
    
    function setupBulkSwitch() {
        // Ensure toggleSwitch is selected correctly
        const toggleSwitch = document.getElementById('bulkSwitch'); // Make sure to use the correct ID
    
        // Check if there is a saved state in localStorage
        const savedState = localStorage.getItem('dz_bulkSwitchState');
        
        // If no saved state is found, set the checkbox state and save it to localStorage
        if (savedState === null) {
            // Save the current state (whether checked or not) to localStorage
            localStorage.setItem('dz_bulkSwitchState', toggleSwitch.checked);
        } else {
            // If there's a saved state, use it
            toggleSwitch.checked = savedState === 'true';
        }
    
        // Apply the Tabulator class based on the saved state
        toggleTabulatorClass(toggleSwitch.checked);
    
        // Event listener to update the saved state when the switch is changed
        toggleSwitch.addEventListener('change', () => {
            const isChecked = toggleSwitch.checked;
            toggleTabulatorClass(isChecked); // Apply the tabulator class based on the new state
            localStorage.setItem('dz_bulkSwitchState', isChecked); // Save the new state to localStorage
        });
    }
    
    // Initial setup
    setupToggleListeners();
    setupBulkSwitch();
    
    
}