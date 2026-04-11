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
