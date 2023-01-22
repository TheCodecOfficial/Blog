/*let words = document.getElementsByClassName("cm-word");
// For each word, check if value is "float2"
for (let i = 0; i < words.length; i++) {
    if (words[i].innerText == "float2") {
        // If so, change the class from cm-word to cm-keyword
        words[i].className = "cm-keyword";
    }
}*/

function copyText() {
    var Text = document.getElementById("textbox");
    Text.select();
    navigator.clipboard.writeText(Text.value);
    document.getElementById("copyInfo").style.display = "inline";
}