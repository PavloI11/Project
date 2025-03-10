document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("photoModal");
    const modalImg = document.getElementById("fullSizeImage");

    window.openModal = function (imageUrl) {
        modal.style.display = "flex";
        setTimeout(() => modal.classList.add("show"), 10);
        modalImg.src = imageUrl;
    };

    window.closeModal = function () {
        modal.classList.remove("show");
        setTimeout(() => modal.style.display = "none", 300);
    };

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeModal();
        }
    });
});
