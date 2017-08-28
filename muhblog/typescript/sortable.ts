class FileTable {
    element: HTMLTableElement;
    head: HTMLTableSectionElement;
    body: HTMLTableSectionElement;
    columnHeaders: Header[];

    constructor(selector: string) {
        this.columnHeaders = [];
        this.element = <HTMLTableElement>document.querySelector(selector);
        this.head = <HTMLTableSectionElement>this.element.querySelector("thead");
        this.body = <HTMLTableSectionElement>this.element.querySelector("tbody");
    }

    get sortedColumnHeader() : Header | null {
        return this.columnHeaders.find(header => header.sortState !== HeaderSortState.unsorted)
            || null;
    }

    get sortState() : HeaderSortState {
        let header = this.sortedColumnHeader;
        return header === null ? HeaderSortState.unsorted : header.sortState;
    }

    initialiseColumnHeader(selector: string,
                    sortKey: (row: HTMLTableRowElement) => any) : Header {
        let element = <HTMLTableHeaderCellElement>this.head.querySelector(selector);
        let header = new Header(element, sortKey);
        element.addEventListener("click", event => {
            this.sortByNewHeader(header, this.sortState === HeaderSortState.descending);
        });
        this.columnHeaders.push(header);
        return header;
    }

    sort(header: Header, ascending: boolean) : void {
        let rows = Array.from(this.body.getElementsByTagName("tr"))
            .map(row => <HTMLTableRowElement>row);

        rows.sort((rowA, rowB) => {
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
        rows.forEach(row => {
            let clone = row.cloneNode(true);
            this.body.appendChild(clone);
        });
    }

    sortByNewHeader(sortHeader: Header, ascending: boolean) : void {
        this.columnHeaders.forEach(header => header.sortState = HeaderSortState.unsorted);
        sortHeader.sortState = ascending ? HeaderSortState.ascending
            : HeaderSortState.descending;
        this.sort(sortHeader, ascending);
    }

    reSortSameHeader() : void {
        let sortedColumnHeader = <Header>this.sortedColumnHeader;
        this.sort(sortedColumnHeader, sortedColumnHeader.sortState === HeaderSortState.ascending);
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
