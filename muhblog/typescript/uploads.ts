document.addEventListener("DOMContentLoaded", () => {
    let table = new FileTable("#uploads table");
    table.initialiseColumnHeader("#name", row => {
        let link = <HTMLLinkElement>row.querySelector(".name a");
        return link.innerText;
    });
    table.initialiseColumnHeader("#size", row => {
        let cell = <HTMLTableDataCellElement>row.querySelector(".size");
        let sizeAttribute = <string>cell.getAttribute("data-size");
        return Number.parseInt(sizeAttribute);
    });
    table.initialiseColumnHeader("#date-modified", row => {
        let element = <HTMLTimeElement>row
            .querySelector(".date-modified time");
        return <string>element.getAttribute("datetime");
    });
    table.reSortSameHeader();
});
