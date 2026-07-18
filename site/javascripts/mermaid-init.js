mermaid.initialize({
  startOnLoad: false,
  theme: "default",
});

document$.subscribe(() => {
  mermaid.run({
    nodes: document.querySelectorAll(".mermaid"),
  });
});
