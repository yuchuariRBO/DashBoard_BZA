/* Keep table scrolling local and keyboard accessible, including inserted results. */
(() => {
  const prepareTables = () => {
    document.querySelectorAll('main table').forEach((table) => {
      if (table.closest('.workday-wrap')) return; // Paired panes have their own scroll model.
      let region = table.closest('.table-responsive, .table-container');
      if (!region) {
        region = document.createElement('div');
        region.className = 'table-responsive';
        table.before(region);
        region.append(table);
      }
      if (!region.hasAttribute('tabindex')) region.tabIndex = 0;
      if (!region.hasAttribute('role')) region.setAttribute('role', 'region');
      if (!region.hasAttribute('aria-label')) region.setAttribute('aria-label', 'Tabla con desplazamiento horizontal');
    });
  };
  prepareTables();
  const main = document.querySelector('main');
  if (main) new MutationObserver(prepareTables).observe(main, { childList: true, subtree: true });
})();
