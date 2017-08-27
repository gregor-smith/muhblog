class FileTable {
    headers: Header[];
    body: HTMLTableSectionElement;
    rows: HTMLTableRowElement[];

    constructor() {
        this.headers = [];
        this.body = <HTMLTableSectionElement>document.getElementById("body");
        this.rows = Array.from(this.body.getElementsByTagName("tr"))
            .map(row => <HTMLTableRowElement>row.cloneNode(true));

        this.initaliseHeader("name", row => {
            let link = <HTMLLinkElement>row.querySelector(".name a");
            return link.innerText;
        });
        this.initaliseHeader("size", row => {
            let cell = <HTMLTableDataCellElement>row.querySelector(".size");
            let sizeAttribute = <string>cell.getAttribute("data-size");
            return Number.parseInt(sizeAttribute);
        });
        this.initaliseHeader("date-modified", row => {
            let element = <HTMLTimeElement>row
                .querySelector(".date-modified time");
            return <string>element.getAttribute("datetime");
        });
    }

    get sortedHeader() : Header | null {
        for (let header of this.headers) {
            if (header.sortState !== HeaderSortState.unsorted) {
                return header;
            }
        }
        return null;
    }

    get sortState() : HeaderSortState {
        let header = this.sortedHeader;
        return header === null ? HeaderSortState.unsorted : header.sortState;
    }

    initaliseHeader(id: string,
                    sortKey: (row: HTMLTableRowElement) => any) : Header {
        let element = <HTMLTableHeaderCellElement>document.getElementById(id);
        let header = new Header(element, sortKey);
        element.addEventListener("click", event => {
            this.sortAndChangeClass(header, this.sortState === HeaderSortState.descending);
        });
        this.headers.push(header);
        return header;
    }

    sort(header: Header, ascending: boolean) : void {
        this.rows.sort((rowA, rowB) => {
            let keyA = header.sortKey(rowA);
            let keyB = header.sortKey(rowB);
            if (keyA === keyB) {
                return 0;
            }
            if (keyA > keyB) {
                return ascending ? 1 : -1;
            }
            return ascending ? -1 : 1;
        });

        while (this.body.firstChild) {
            this.body.removeChild(this.body.firstChild);
        }
        for (let row of this.rows) {
            let clone = row.cloneNode(true);
            this.body.appendChild(clone);
        }
    }

    sortAndChangeClass(sortHeader: Header, ascending: boolean) : void {
        for (let header of this.headers) {
            header.sortState = HeaderSortState.unsorted;
        }
        sortHeader.sortState = ascending ? HeaderSortState.ascending
            : HeaderSortState.descending;
        this.sort(sortHeader, ascending);
    }

    reSort() : void {
        let sortedHeader = <Header>this.sortedHeader;
        this.sort(sortedHeader, sortedHeader.sortState === HeaderSortState.ascending);
    }
}


enum HeaderSortState {
    unsorted,
    ascending,
    descending
}


class Header {
    element: HTMLTableHeaderCellElement;
    sortKey: ((row: HTMLTableRowElement) => any);

    constructor(element: HTMLTableHeaderCellElement,
                sortKey: (row: HTMLTableRowElement) => any) {
        this.element = element;
        this.sortKey = sortKey;
    }

    get sortState() : HeaderSortState {
        for (let index = 0; index < this.element.classList.length; index++) {
            let cls = this.element.classList.item(index);
            if (cls === "sort-ascending") {
                return HeaderSortState.ascending;
            }
            if (cls === "sort-descending") {
                return HeaderSortState.descending;
            }
        }
        return HeaderSortState.unsorted;
    }

    set sortState(value: HeaderSortState) {
        this.element.classList.remove("sort-ascending");
        this.element.classList.remove("sort-descending");
        if (value === HeaderSortState.ascending) {
            this.element.classList.add("sort-ascending");
        }
        else if (value === HeaderSortState.descending) {
            this.element.classList.add("sort-descending");
        }
    }
}


document.addEventListener("DOMContentLoaded", () => {
    let table = new FileTable();
    table.reSort();
});
