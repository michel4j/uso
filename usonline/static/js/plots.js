/**
 * Created by michel on 06/06/16.
 */

function table_plot(plotid, data, types, colors){
    nv.addGraph(function() {
        var chart = nv.models.multiBarChart()
          .transitionDuration(250)
          .reduceXTicks(false)   //If 'false', every single x-axis tick label will be rendered.
          .rotateLabels(-45)      //Angle to rotate x-axis labels.
          .showControls(true)   //Allow user to switch between 'Grouped' and 'Stacked' mode.
          .groupSpacing(0.05)    //Distance between each group of bars.
          .showLegend(false)
          .stacked(false)
          .rightAlignYAxis(true)
          .margin({right: 35, left: 0})
        ;

        chart.xAxis.tickFormat(d3.format('f'));
        chart.yAxis.tickFormat(d3.format('f'));

        d3.select('#chart-'+plotid + ' svg')
            .datum(data)
            .call(chart);

        nv.utils.windowResize(chart.update);
        return chart;
    });

    //Adjust size
    var chel = $('#chart-' + plotid).find('svg');
    var table_pos = $('#table-' + plotid + ' table:nth-of-type(1)').position();
    chel.width(chel.parent().width());
    chel.height(chel.parent().width()*10/16);
    chel.css('margin-top', table_pos.top + 'px');

    // Fix table colors
    var tbl = $('#table-' + plotid + ' table');
    for (i = 0; i < types.length; i++) {
        var td = tbl.find("td:contains('"+types[i]+"')");
        td.css({"color": colors[i], "font-weight": "bold", "line-height": 1});
    }

}

function truncate(str, maxLength, suffix) {
    if (str.length > maxLength) {
        str = str.substring(0, maxLength + 1);
        str = str.substring(0, Math.min(str.length, str.lastIndexOf(" ")));
        str = str + suffix;
    }
    return str;
}

function bubble_table(el, url) {
    var margin = {top: 20, right: 200, bottom: 0, left: 20},
        width = 800,
        height = 650;

    var start_year = 1970,
        end_year = 2013;

    var c = d3.scale.category20c();

    var x = d3.scale.linear()
        .range([0, width]);

    var xAxis = d3.svg.axis()
        .scale(x)
        .orient("top");

    var formatYears = d3.format("0000");
    xAxis.tickFormat(formatYears);

    var svg = d3.select(el).append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .style("margin-left", margin.left + "px")
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");


    d3.json(url, function (data) {
        x.domain([start_year, end_year]);
        var xScale = d3.scale.linear()
            .domain([start_year, end_year])
            .range([0, width]);

        svg.append("g")
            .attr("class", "x axis")
            .attr("transform", "translate(0," + 0 + ")")
            .call(xAxis);

        for (var j = 0; j < data.length; j++) {
            var g = svg.append("g").attr("class", "journal");

            var circles = g.selectAll("circle")
                .data(data[j]['articles'])
                .enter()
                .append("circle");

            var text = g.selectAll("text")
                .data(data[j]['articles'])
                .enter()
                .append("text");

            var rScale = d3.scale.linear()
                .domain([0, d3.max(data[j]['articles'], function (d) {
                    return d[1];
                })])
                .range([2, 9]);

            circles
                .attr("cx", function (d, i) {
                    return xScale(d[0]);
                })
                .attr("cy", j * 20 + 20)
                .attr("r", function (d) {
                    return rScale(d[1]);
                })
                .style("fill", function (d) {
                    return c(j);
                });

            text
                .attr("y", j * 20 + 25)
                .attr("x", function (d, i) {
                    return xScale(d[0]) - 5;
                })
                .attr("class", "value")
                .text(function (d) {
                    return d[1];
                })
                .style("fill", function (d) {
                    return c(j);
                })
                .style("display", "none");

            g.append("text")
                .attr("y", j * 20 + 25)
                .attr("x", width + 20)
                .attr("class", "label")
                .text(truncate(data[j]['name'], 30, "..."))
                .style("fill", function (d) {
                    return c(j);
                })
                .on("mouseover", mouseover)
                .on("mouseout", mouseout);
        }

        function mouseover(p) {
            var g = d3.select(this).node().parentNode;
            d3.select(g).selectAll("circle").style("display", "none");
            d3.select(g).selectAll("text.value").style("display", "block");
        }

        function mouseout(p) {
            var g = d3.select(this).node().parentNode;
            d3.select(g).selectAll("circle").style("display", "block");
            d3.select(g).selectAll("text.value").style("display", "none");
        }
    });
}
