(function () {
  'use strict';

  // The two booking forms use <input type="file" multiple>. Browsers replace
  // the FileList when the file picker is opened again. Keep a local collection
  // and write the accumulated files back to the input before the existing
  // change handlers run.
  var INPUT_IDS = ['photo-input', 'appointment-photos'];
  var MAX_FILES = 5;
  var state = new WeakMap();

  function keyFor(file) {
    return [file.name, file.size, file.lastModified, file.type].join('|');
  }

  function setFiles(input, files) {
    if (typeof DataTransfer === 'undefined') {
      return;
    }

    var transfer = new DataTransfer();
    files.slice(0, MAX_FILES).forEach(function (file) {
      transfer.items.add(file);
    });
    input.files = transfer.files;
  }

  function handleChange(event) {
    var input = event.target;
    if (!input || INPUT_IDS.indexOf(input.id) === -1 || !input.multiple) {
      return;
    }

    var current = Array.prototype.slice.call(input.files || []);
    var saved = state.get(input) || [];
    var seen = Object.create(null);
    var combined = [];

    saved.concat(current).forEach(function (file) {
      var key = keyFor(file);
      if (!seen[key] && combined.length < MAX_FILES) {
        seen[key] = true;
        combined.push(file);
      }
    });

    state.set(input, combined);
    setFiles(input, combined);
  }

  // Capture phase is intentional: the accumulated FileList must be installed
  // before the page-specific preview/change handler receives the same event.
  document.addEventListener('change', handleChange, true);

  document.addEventListener('reset', function (event) {
    var form = event.target;
    if (!form || !form.querySelector) {
      return;
    }

    INPUT_IDS.forEach(function (id) {
      var input = form.querySelector('#' + id);
      if (input) {
        state.delete(input);
      }
    });
  }, true);
})();
