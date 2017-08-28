class FileTable {
    element: HTMLTableElement;
    head: HTMLTableSectionElement;
    body: HTMLTableSectionElement;
    columnHeaders: ColumnHeader[];

    /**
     * @param selector Passed to `document.querySelector` to find
     *                 the `<table>` `HTMLTableElement`.
     */
    constructor(selector: string) {
        this.columnHeaders = [];
        this.element = <HTMLTableElement>document.querySelector(selector);
        this.head = <HTMLTableSectionElement>this.element.querySelector("thead");
        this.body = <HTMLTableSectionElement>this.element.querySelector("tbody");
    }

    /**
     * @returns The first [[ColumnHeader]] whose [[ColumnHeader.sortState]] is not
     *          [[ColumnHeaderSortState.unsorted]], or `null` if none are found.
     */
    get sortedColumnHeader() : ColumnHeader | null {
        return this.columnHeaders.find(header => header.sortState !== ColumnHeaderSortState.unsorted)
            || null;
    }

    /**
     * @returns The `sortState` of the current [[sortedColumnHeader]],
     *          or [[ColumnHeaderSortState.unsorted]] if no header is currently
     *          sorted.
     */
    get sortState() : ColumnHeaderSortState {
        let header = this.sortedColumnHeader;
        return header === null ? ColumnHeaderSortState.unsorted : header.sortState;
    }

    /**
     * Adds a `click` event listener to the `<th>` element matching `selector`.
     * Upon the event firing, the table is sorted by that column, with
     * `sortKey` used to compare rows.
     * @param selector The selector used to find the column header,
     *                 relative to the table's `<thead>`.
     * @param sortKey A function that when given a row returns a key by which
     *                to compare other rows. For example, to compare two
     *                rows by a column's attribute, it should return
     *                `row.querySelector("#a-column")
     *                     .getAttribute("an-attribute")`
     */
    initialiseColumnHeader(selector: string,
                           sortKey: (row: HTMLTableRowElement) => any) : ColumnHeader {
        let element = <HTMLTableHeaderCellElement>this.head.querySelector(selector);
        let header = new ColumnHeader(element, sortKey);
        element.addEventListener("click", event => {
            this.sortByNewHeader(header, this.sortState === ColumnHeaderSortState.descending);
        });
        this.columnHeaders.push(header);
        return header;
    }

    private sort(header: ColumnHeader, ascending: boolean) : void {
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

    /**
     * Called by a [[ColumnHeader.element]]'s click event, added by
     * [[initialiseColumnHeader]]. Sorts the table and sets the appropriate
     * class for the [[ColumnHeader]]'s `<th>` element.
     * @param sortHeader The [[ColumnHeader]] to sort by.
     * @param ascending Whether to sort in ascending order.
     */
    sortByNewHeader(sortHeader: ColumnHeader, ascending: boolean) : void {
        this.columnHeaders.forEach(header => header.sortState = ColumnHeaderSortState.unsorted);
        sortHeader.sortState = ascending ? ColumnHeaderSortState.ascending
            : ColumnHeaderSortState.descending;
        this.sort(sortHeader, ascending);
    }

    /**
     * Re-sorts by whichever [[ColumnHeader]] is already the [[sortedColumnHeader]].
     * Use for the initial sort upon loading the page, when `.sort-ascending`
     * or `.sort-descending` has been set in the HTML template rather than by a
     * user event.
     */
    reSortSameHeader() : void {
        let sortedColumnHeader = <ColumnHeader>this.sortedColumnHeader;
        this.sort(sortedColumnHeader, sortedColumnHeader.sortState === ColumnHeaderSortState.ascending);
    }
}


enum ColumnHeaderSortState {
    /** The `<th>` element has neither the `.sort-ascending`
     *  nor `.sort-descending` class. */
    unsorted,
    /** The `<th>` element has the `.sort-ascending` class. */
    ascending,
    /** The `<th>` element has the `.sort-descending` class. */
    descending
}


class ColumnHeader {
    /** The underlying `<th>` element. */
    element: HTMLTableHeaderCellElement;
    /** Function used to compare rows.
     *  See [[FileTable.initialiseColumnHeader]]. */
    sortKey: ((row: HTMLTableRowElement) => any);

    constructor(element: HTMLTableHeaderCellElement,
                sortKey: (row: HTMLTableRowElement) => any) {
        this.element = element;
        this.sortKey = sortKey;
    }

    /**
     * @returns [[ColumnHeaderSortState.unsorted]] if [[element]] has neither
     *          the `.sort-ascending` nor `.sort-descending` class.
     *          [[ColumnHeaderSortState.ascending]] if [[element]] has the
     *          `.sort-ascending` class.
     *          [[ColumnHeaderSortState.ascending]] if [[element]] has the
     *          `.sort-descending` class.
     */
    get sortState() : ColumnHeaderSortState {
        for (let index = 0; index < this.element.classList.length; index++) {
            let cls = this.element.classList.item(index);
            if (cls === "sort-ascending") {
                return ColumnHeaderSortState.ascending;
            }
            if (cls === "sort-descending") {
                return ColumnHeaderSortState.descending;
            }
        }
        return ColumnHeaderSortState.unsorted;
    }

    /** Sets [[element]]'s class. */
    set sortState(value: ColumnHeaderSortState) {
        this.element.classList.remove("sort-ascending");
        this.element.classList.remove("sort-descending");
        if (value === ColumnHeaderSortState.ascending) {
            this.element.classList.add("sort-ascending");
        }
        else if (value === ColumnHeaderSortState.descending) {
            this.element.classList.add("sort-descending");
        }
    }
}
