window.initIndexJS = function() {

    const dropDialog = document.getElementById('drop-dialog');
    const loadingDialog = document.getElementById('loading-dialog');
    const dropArea = document.getElementById('drop-area');
    const fileInput = document.getElementById('fileElem');
    const btnUpload = document.getElementById('btn_upload');

    // Error dialog
    const errorDialog = document.getElementById('error-dialog'); // Select the error dialog
    const errorText = errorDialog.querySelector('.card-text'); // Select the {ERROR_TEXT} container

    // XML Error dialog
    const xml_errorDialog = document.getElementById('xml_error'); // Select the error dialog
    const xml_errorText = document.getElementById('xml_error_text'); // Select the {ERROR_TEXT} container

    // Prevent default behaviors for drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(e => {
        dropArea.addEventListener(e, preventDefaults, false);  
        document.body.addEventListener(e, preventDefaults, false);  
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight the drop area when dragging files over
    ['dragenter', 'dragover'].forEach(e => {
        dropArea.addEventListener(e, highlight, false);
    });
    ['dragleave', 'drop'].forEach(e => {
        dropArea.addEventListener(e, unhighlight, false);
    });

    function highlight() {
        dropArea.classList.add('drop-area-active');
    }

    function unhighlight() {
        dropArea.classList.remove('drop-area-active');
    }

    // Handle dropped files
    dropArea.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files; 
        handleFiles(files);
    });

    // Open file dialog when drop area is clicked
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });

    // Open file dialog when upload button is clicked
    btnUpload.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file input change
    fileInput.addEventListener('change', () => {
        handleFiles(fileInput.files);
    });

    // Function to process files
    function handleFiles(files) {
        [...files].forEach(uploadFile);
        dropDialog.classList.add('visually-hidden');
        loadingDialog.classList.remove('visually-hidden');
    }

    // Upload a file
    async function uploadFile(file) {

        const url = 'backend/upload.php';
        const formData = new FormData();
        formData.append('file', file);
    
        // Check the state of the checkbox
        const bypassCheckbox = document.getElementById('sw_bypassValidation');
        if (bypassCheckbox.checked) {
            formData.append('bypass', bypassCheckbox.value);
        }
    
        try {
            const response = await fetch(url, {
                method: "POST",
                body: formData,
            });
    
            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
    
            const responseText = await response.text();
            const responseJSON = JSON.parse(responseText);
    
            // XML error
            if (responseJSON.error) {
                if (responseJSON.error.toLowerCase().includes('line')) {
                    xml_errorDialog.classList.remove('visually-hidden');
                    xml_errorText.innerHTML = responseJSON.error;
                    return;
                }
            }
    
            // Check for success in response text
            if (responseJSON.data && responseJSON.data.toLowerCase().includes('valid')) {
                window.location.href = "editor.php"; // Redirect after success
                return;
            }
    
            if (responseJSON.error !== "") {
                throw new Error(responseJSON.error); // If response indicates failure
            }
    
        } catch (error) {
            errorText.innerHTML = `<strong>Upload failed:</strong> ${error.message}`; // Display error message in {ERROR_TEXT}
            errorDialog.classList.remove('visually-hidden'); // Show error dialog
            throw new Error(error); // If response indicates failure
        } finally {
            loadingDialog.classList.add('visually-hidden'); // Hide loading dialog in any case
        }
    }    
}
