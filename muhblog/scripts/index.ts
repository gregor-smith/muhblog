import '../style/main.scss'


document.querySelectorAll('img[data-lazy-url]')
    .forEach(element => {
        const url = element.getAttribute('data-lazy-url')
        if (url === null) {
            return
        }
        const observer = new IntersectionObserver(entries => {
            if (!entries.some(entry => entry.isIntersecting)) {
                return
            }
            element.setAttribute('src', url)
            observer.disconnect()
        })
        observer.observe(element)
    })
