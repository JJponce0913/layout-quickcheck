function printDimensions(node, fields) {{
    let dims = node.getBoundingClientRect();
    console.log("#" + node.id, Object.fromEntries(fields.map((x) => [x, dims[x]])));
}}

// Make the style changes to the page
function makeStyleChanges() {{
    {make_style_changes}
}}

function fromScratchLayout() {{
    document.documentElement.innerHTML = document.documentElement.innerHTML;
}}

function simpleRecreate() {{
    console.log("Make changes and perform incremental layout");
    makeStyleChanges();
    {get_dimensions}

    // Reload the elements
    console.log("Perform from scratch layout, below values should differ from above");
    fromScratchLayout();
    {get_dimensions}
}}
