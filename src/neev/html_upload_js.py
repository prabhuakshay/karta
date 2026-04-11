"""Client-side JavaScript for the upload UI.

Contains the Alpine.js component logic for drag-and-drop uploads,
file preview, and relative path population for folder uploads.
"""


def get_upload_script() -> str:
    """Return the <script> tag for upload interactivity.

    Returns:
        Complete ``<script>`` element with Alpine component registration.
    """
    return _UPLOAD_SCRIPT


_UPLOAD_SCRIPT = """\
<script>
document.addEventListener('alpine:init', function() {
  Alpine.data('uploadZone', function() {
    return {
      mode: 'files',
      dragging: false,
      files: [],
      uploading: false,
      pastedFiles: null,

      switchMode: function(m) {
        this.mode = m;
        this.clearFiles();
      },

      handleDrop: function(ev) {
        this.dragging = false;
        var dt = ev.dataTransfer;
        if (dt && dt.files && dt.files.length) this.setFiles(dt.files);
      },

      handleFiles: function(ev) {
        if (ev.target.files.length) this.setFiles(ev.target.files);
      },

      handlePaste: function(ev) {
        var items = ev.clipboardData && ev.clipboardData.items;
        if (!items) return;
        var dt = new DataTransfer();
        for (var i = 0; i < items.length; i++) {
          if (items[i].kind !== 'file') continue;
          var f = items[i].getAsFile();
          if (!f) continue;
          if (!f.name || f.name === 'image.png') {
            var ext = (f.type.split('/')[1] || 'png').replace('+xml', '');
            var ts = new Date().toISOString().replace(/[:.]/g, '-')
              .slice(0, 19);
            var named = new File([f], 'paste-' + ts + '.' + ext,
              { type: f.type });
            dt.items.add(named);
          } else {
            dt.items.add(f);
          }
        }
        if (dt.files.length) {
          this.pastedFiles = dt;
          this.setFiles(dt.files);
        }
      },

      setFiles: function(list) {
        this.files = [];
        for (var i = 0; i < list.length; i++) {
          this.files.push({
            name: list[i].webkitRelativePath || list[i].name,
            size: list[i].size
          });
        }
        this.populateRelPaths();
      },

      removeFile: function(idx) {
        this.files.splice(idx, 1);
        if (!this.files.length) this.clearFiles();
      },

      clearFiles: function() {
        this.files = [];
        this.pastedFiles = null;
        var inputs = this.$refs.uploadForm.querySelectorAll(
          'input[type="file"]'
        );
        for (var i = 0; i < inputs.length; i++) inputs[i].value = '';
        this.clearRelPaths();
      },

      formatSize: function(b) {
        if (b < 1024) return b + ' B';
        if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
        return (b / 1048576).toFixed(1) + ' MB';
      },

      clearRelPaths: function() {
        var c = document.getElementById('relativePathFields');
        while (c.firstChild) c.removeChild(c.firstChild);
      },

      populateRelPaths: function() {
        this.clearRelPaths();
        if (this.pastedFiles) {
          var fileInput = this.$refs.uploadForm.querySelector(
            'input[name="file"][multiple]'
          );
          if (fileInput) fileInput.files = this.pastedFiles.files;
          return;
        }
        var c = document.getElementById('relativePathFields');
        var inputs = this.$refs.uploadForm.querySelectorAll(
          'input[type="file"]'
        );
        for (var i = 0; i < inputs.length; i++) {
          var inp = inputs[i];
          if (!inp.offsetParent && inp.style.display === 'none') continue;
          for (var j = 0; j < inp.files.length; j++) {
            var rp = inp.files[j].webkitRelativePath || '';
            if (rp) {
              var h = document.createElement('input');
              h.type = 'hidden';
              h.name = 'relativePath';
              h.value = rp;
              c.appendChild(h);
            }
          }
          break;
        }
      }
    };
  });
});
</script>"""
