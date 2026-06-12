// EduCore - Main JavaScript

function copyInviteLink() {
    var linkInput = document.getElementById('inviteLink');
    if (linkInput) {
        navigator.clipboard.writeText(linkInput.value).then(function() {
            // Tugmani vaqtincha o'zgartirish
            var btn = linkInput.nextElementSibling;
            var originalText = btn.textContent;
            btn.textContent = 'Nusxalandi!';
            btn.classList.remove('btn-outline-primary');
            btn.classList.add('btn-success');
            setTimeout(function() {
                btn.textContent = originalText;
                btn.classList.remove('btn-success');
                btn.classList.add('btn-outline-primary');
            }, 2000);
        }).catch(function() {
            // Fallback: select va copy
            linkInput.select();
            linkInput.setSelectionRange(0, 99999);
            document.execCommand('copy');
            alert('Havola nusxalandi!');
        });
    }
}
