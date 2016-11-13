var textExtraction = function(node) {
    switch (node.className) {
        case "modified":
            return node.getElementsByTagName("time")[0]
                .getAttribute("datetime");
        case "size":
            return node.dataset.size;
        case "name":
            return node.getElementsByTagName("a")[0]
                .innerText;
    }
}

$(document).ready(
    function() {
        $("table").tablesorter(
            {textExtraction: textExtraction,
             dateFormat: "yyyy-mm-dd"}
        );
    }
);