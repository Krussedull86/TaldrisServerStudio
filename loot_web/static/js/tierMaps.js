window.initTierMapsJS = function() {

    const draggableDiv = document.getElementById("draggableDiv");
    const toggleButton = document.getElementById("btn_tierMaps");
    const closeButton = draggableDiv.querySelector(".closeButton");
    const header = draggableDiv.querySelector(".header");
    const imageSelector = document.getElementById("imageSelector");
    const displayImage = document.getElementById("displayImage");

    let isDragging = false;
    let offsetX = 0;
    let offsetY = 0;

    // Function to center the div
    function centerDiv() {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const divWidth = draggableDiv.offsetWidth;
    const divHeight = draggableDiv.offsetHeight;

    const left = (viewportWidth - divWidth) / 2;
    const top = (viewportHeight - divHeight) / 2;

    draggableDiv.style.left = `${left}px`;
    draggableDiv.style.top = `${top}px`;
    }

    // Toggle visibility and center
    toggleButton.addEventListener("click", () => {
    if (draggableDiv.classList.contains("hidden")) {
        draggableDiv.classList.remove("hidden");
        centerDiv(); // Center the div when opening
    } else {
        draggableDiv.classList.add("hidden");
    }
    });

    // Close button functionality
    closeButton.addEventListener("click", () => {
    draggableDiv.classList.add("hidden");
    });

    // Drag functionality
    header.addEventListener("mousedown", (e) => {
    isDragging = true;
    offsetX = e.clientX - draggableDiv.offsetLeft;
    offsetY = e.clientY - draggableDiv.offsetTop;
    draggableDiv.style.cursor = "grabbing";
    });

    document.addEventListener("mousemove", (e) => {
    if (isDragging) {
        draggableDiv.style.left = `${e.clientX - offsetX}px`;
        draggableDiv.style.top = `${e.clientY - offsetY}px`;
    }
    });

    document.addEventListener("mouseup", () => {
    isDragging = false;
    draggableDiv.style.cursor = "grab";
    });

    // Ensure it's always on top when clicked
    draggableDiv.addEventListener("mousedown", () => {
    draggableDiv.style.zIndex = `${parseInt(draggableDiv.style.zIndex) + 1}`;
    });

    // Re-center the div when the window resizes
    window.addEventListener("resize", () => {
    if (!draggableDiv.classList.contains("hidden")) {
        centerDiv();
    }
    });

    // Change image on dropdown selection
    imageSelector.addEventListener("change", () => {
    const selectedImage = imageSelector.value;
    displayImage.src = selectedImage;
    });
}
