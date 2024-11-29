// MathJas Config
window.MathJax = {
    options: {
        enableMenu: false
    }
};

(function () {
    let script = document.createElement('script');
    //script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/MathJax.js?config=TeX-AMS_SVG';
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/4.0.0-beta.7/tex-svg.min.js';
    script.async = true;
    document.head.appendChild(script);
})();