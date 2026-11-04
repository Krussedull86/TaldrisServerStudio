window.initValidateJS = function() {

    const fileInputTypes = document.getElementById('fileElemTypes');
    const btnValidateTypes = document.getElementById('btn_validate_types');
    const validationDialog = document.getElementById('validation-dialog');
    const loadingDialog = document.getElementById('loading-dialog');
    const validDialog = document.getElementById('valid-dialog');

    // Error dialog
    const errorDialog = document.getElementById('error-dialog'); // Select the error dialog
    const errorText = errorDialog.querySelector('.card-text'); // Select the {ERROR_TEXT} container

    // XML Error dialog
    const xml_errorDialog = document.getElementById('xml_error'); // Select the error dialog
    const xml_errorText = document.getElementById('xml_error_text'); // Select the {ERROR_TEXT} container

    btnValidateTypes.addEventListener('click', () => {
        fileInputTypes.click();
    });
    // Handle file input change
    fileInputTypes.addEventListener('change', () => {
        handleTypesFile(fileInputTypes.files);
    });

    // Function to process files
    function handleTypesFile(files) {
        [...files].forEach(uploadTypes);
        validationDialog.classList.add('visually-hidden');
        loadingDialog.classList.remove('visually-hidden');
    }

    // Validate
    async function uploadTypes(file) {

        const url = 'backend/validate.php';
        const formData = new FormData();
        formData.append('file', file);

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
                validDialog.classList.remove('visually-hidden');
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