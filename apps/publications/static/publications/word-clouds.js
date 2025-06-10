function wordCloud(data, element, params) {
    if (!data || !data.length) {
        return;
    }
    let defaults = {
        aspectRatio: 16 / 9,
        searchURL: null, // URL to redirect to when a word is clicked
        searchParam: 'search'
    };

    let options = Object.assign({}, defaults, params);
    const fill = d3.scale.category20();
    const w = Math.min($(element).width() * 0.98, 1000), h = w / options.aspectRatio;
    const fscale = w < 600 ? 0.85 : 1;

    d3.layout.cloud().size([w, h])
        .words(data)
        .rotate(function () {
            return ~~(Math.random() * 2) * 90;
        })
        .fontSize(function (d) {
            return d.size * fscale;
        })
        .on("end", draw)
        .start();

    function draw(words) {
        d3.select(element).append("svg")
            .attr("width", w)
            .attr("height", h)
            .append("g")
            .attr("transform", "translate(" + [w >> 1, h >> 1] + ")")
            .selectAll("text")
            .data(words)
            .enter().append("text")
            .style("font-size", function (d) {
                return d.size * fscale + "px";
            })
            .on("click", function (d) {
                if (options.searchURL) {
                    window.location.href = `${options.searchURL}?${options.searchParam}=${d.text}`;
                }
            })
            .style("cursor", "pointer")
            .style("text-transform", "lowercase")
            .style("fill", function (d, i) {
                return fill(i);
            })
            .attr("text-anchor", "middle")
            .attr("transform", function (d) {
                return "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")";
            })
            .text(function (d) {
                return d.text;
            });
    }
}