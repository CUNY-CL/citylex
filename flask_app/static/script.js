document.addEventListener("DOMContentLoaded", function () {
  const e = document.getElementById("selectAll"),
    c = document.getElementById("selectNone"),
    n = document.querySelectorAll("input[name='sources[]']"),
    t = document.querySelectorAll("input[name='fields[]']"),
    r = document.querySelectorAll("input[name='licenses']"),
    l = {
      BY: "CC BY 4.0",
      NC: "CC BY-NC 4.0",
      GNU: "GNU GPL v3",
      apache: "Apache 2.0",
      celex: "CELEX 2 User Agreement",
    },
    o = {
      subtlexus: "NC",
      subtlexuk: "NC",
      UDLexicons: "GNU",
      UniMorph: "BY",
      "WikiPron US": "apache",
      "WikiPron UK": "apache",
      ELP: "NC",
      celexfreq: "celex",
      celexfeat: "celex",
      celexpron: "celex",
    },
    s = {
      subtlexuk: "subtlexuk_raw_frequency",
      subtlexus: "subtlexus_raw_frequency",
      UDLexicons: "udlex_UDtags",
      UniMorph: "um_UMtags",
      "WikiPron US": "wikipronus_IPA",
      "WikiPron UK": "wikipronuk_IPA",
      ELP: "elp_segmentation",
      celexfreq: "celexfreq_raw_frequency",
      celexfeat: "celex_CELEXtags",
      celexpron: "celex_DISC",
    },
    a = [
      "celexfreq_raw_frequency",
      "celexfreq_freq_per_million",
      "celexfreq_logprob",
      "celexfreq_zipf",
      "celex_UDtags",
      "celex_UMtags",
      "celex_CELEXtags",
      "celex_DISC",
    ];
  function i() {
    const e = Array.from(n).filter((e) => e.checked),
      c = new Set(e.map((e) => o[e.value])),
      t = document.getElementById("license-notice");
    if (c.size > 0) {
      const e = Array.from(c)
        .map((e) => {
          const c = l[e];
          let n = "";
          switch (e) {
            case "BY":
              n = "https://creativecommons.org/licenses/by/4.0/";
              break;
            case "NC":
              n = "https://creativecommons.org/licenses/by-nc/4.0/";
              break;
            case "GNU":
              n = "https://www.gnu.org/licenses/gpl-3.0.en.html";
              break;
            case "apache":
              n = "https://www.apache.org/licenses/LICENSE-2.0.html";
              break;
            case "celex":
              n =
                "https://catalog.ldc.upenn.edu/license/celex-user-agreement.pdf";
          }
          return n
            ? `<a href="${n}" target="_blank" rel="noopener noreferrer">${c}</a>`
            : c;
        })
        .join(", ");
      t.innerHTML = `By clicking "Generate and Download," you agree to the terms of the following licenses: ${e}`;
    } else t.innerHTML = "";
  }
  function u() {
    if ("undefined" != typeof PASSWORD_SET && PASSWORD_SET) {
      const e = Array.from(t).some((e) => a.includes(e.value) && e.checked),
        c = document.getElementById("celex-password-section");
      c && (c.style.display = e ? "block" : "none");
    }
  }
  u(),
    n.forEach((e) => {
      e.addEventListener("change", u);
    }),
    e.addEventListener("click", function () {
      n.forEach((e) => (e.checked = !0)),
        t.forEach((e) => (e.checked = !0)),
        r.forEach((e) => (e.checked = !0)),
        i(),
        u();
    }),
    c.addEventListener("click", function () {
      n.forEach((e) => (e.checked = !1)),
        t.forEach((e) => (e.checked = !1)),
        r.forEach((e) => (e.checked = !1)),
        i(),
        u();
    }),
    n.forEach((e) => {
      e.addEventListener("change", function () {
        const c = o[e.value],
          n = document.querySelector(`input[name='licenses'][value='${c}']`),
          t = e.closest("li").querySelectorAll("input[name='fields[]']");
        if (e.checked) {
          n && (n.checked = !0);
          const c = s[e.value];
          t.forEach((e) => {
            e.checked = e.value === c;
          });
        } else t.forEach((e) => (e.checked = !1));
        i(), u();
      });
      const c = e.closest("li").querySelectorAll("input[name='fields[]']");
      function n() {
        const n = Array.from(c).some((e) => e.checked);
        if (((e.checked = n), n)) {
          const c = o[e.value];
          document.querySelector(
            `input[name='licenses'][value='${c}']`
          ).checked = !0;
        }
        u();
      }
      n(),
        c.forEach((e) => {
          e.addEventListener("change", n), e.addEventListener("change", u);
        });
    }),
    t.forEach((e) => {
      e.addEventListener("change", function () {
        const c = e.closest("li").querySelector("input[name='sources[]']");
        e.checked && (c.checked = !0), u();
      });
    }),
    r.forEach((e) => {
      e.addEventListener("change", function () {
        if (!e.checked)
          for (const [c, n] of Object.entries(o))
            if (n === e.value) {
              const e = document.querySelector(
                `input[name='sources[]'][value='${c}']`
              );
              e.checked = !1;
              e.closest("li")
                .querySelectorAll("input[name='fields[]']")
                .forEach((e) => (e.checked = !1));
            }
        u();
      });
    });
});
