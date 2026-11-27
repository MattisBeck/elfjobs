// Stundenplan wie im Kalender (#87): Termine per Ziehen anlegen, verschieben und verlängern.
//
// Ohne Bibliothek, nur Pointer Events. Die Seite liefert die Daten als JSON (#timetable-data),
// gespeichert wird sofort über die Endpunkte in timetable/views.py. Die freien Blöcke rechnet
// der Server und schickt sie nach jeder Änderung mit.
//
// Zeiten sind hier Minuten seit Mitternacht (9:15 = 555). Das Raster geht von 8 bis 20 Uhr
// in Schritten von 15 Minuten.

(function () {
  "use strict";

  var DAY_START = 8 * 60;
  var DAY_END = 20 * 60;
  var STEP = 15;
  var NEW_DURATION = 90; // Tippen (Handy) oder Klick ohne Ziehen legt 90 Minuten an
  var DRAG_THRESHOLD = 4; // so viele Pixel, bevor aus einem Klick ein Verschieben wird
  var DAY_NAMES = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"];
  var DAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr"];

  var editor = document.querySelector("[data-timetable-editor]");
  var dataElement = document.getElementById("timetable-data");
  if (!editor || !dataElement) return;

  var data = JSON.parse(dataElement.textContent);
  var state = {
    lectures: data.lectures.map(fromJson),
    free: data.free.map(fromJson),
    layout: data.layout, // Spalten pro Termin-ID, vom Server (#135)
  };
  var shifts = (data.shifts || []).map(function (item) {
    return Object.assign(fromJson(item), { company: item.company, logoUrl: item.logo_url, initials: item.initials, url: item.url, conflict: item.conflict });
  });
  var urls = data.urls;
  var csrfToken = document.querySelector("[name=csrfmiddlewaretoken]").value;
  var week = editor.querySelector(".tt-week");
  var statusLine = editor.querySelector(".tt-status");
  var freeHours = document.querySelector("[data-free-hours]");

  // Mit JavaScript ersetzt das Raster Liste und Formular.
  editor.hidden = false;
  document.querySelector("[data-timetable-fallback]").hidden = true;

  // --- Zeiten ---------------------------------------------------------------

  function toMinutes(text) {
    var parts = text.split(":");
    return Number(parts[0]) * 60 + Number(parts[1]);
  }

  function toText(minutes) {
    var hours = Math.floor(minutes / 60);
    var rest = minutes % 60;
    return (hours < 10 ? "0" : "") + hours + ":" + (rest < 10 ? "0" : "") + rest;
  }

  // Anzeige wie im Rest der Seite: 9:15–12:30
  function label(start, end) {
    return toText(start).replace(/^0/, "") + "–" + toText(end).replace(/^0/, "");
  }

  function fromJson(item) {
    return {
      id: item.id,
      title: item.title,
      weekday: item.weekday,
      start: toMinutes(item.start),
      end: toMinutes(item.end),
    };
  }

  function clamp(value, low, high) {
    return Math.min(Math.max(value, low), high);
  }

  function percent(minutes) {
    return (clamp(minutes, DAY_START, DAY_END) - DAY_START) / (DAY_END - DAY_START) * 100;
  }

  // Pixel in der Spalte → Minuten, auf 15 Minuten gerundet
  function minutesAt(track, clientY) {
    var rect = track.getBoundingClientRect();
    var minutes = DAY_START + (clientY - rect.top) / rect.height * (DAY_END - DAY_START);
    return clamp(Math.round(minutes / STEP) * STEP, DAY_START, DAY_END);
  }

  function trackAt(clientX) {
    var tracks = week.querySelectorAll(".tt-track");
    for (var i = 0; i < tracks.length; i++) {
      var rect = tracks[i].getBoundingClientRect();
      if (clientX >= rect.left && clientX <= rect.right) return tracks[i];
    }
    return null;
  }

  // --- Zeichnen -------------------------------------------------------------

  function render(focusId) {
    week.textContent = "";

    var axis = document.createElement("div");
    axis.className = "week-axis";
    axis.setAttribute("aria-hidden", "true");
    for (var hour = 8; hour <= 20; hour += 2) {
      var mark = document.createElement("span");
      mark.style.top = percent(hour * 60) + "%";
      mark.textContent = hour;
      axis.appendChild(mark);
    }
    week.appendChild(axis);

    for (var weekday = 0; weekday < 5; weekday++) {
      var day = document.createElement("section");
      day.className = "week-day";
      day.setAttribute("aria-label", DAY_NAMES[weekday]);
      var heading = document.createElement("h3");
      heading.className = "week-day-label";
      heading.textContent = DAY_SHORT[weekday];
      day.appendChild(heading);

      var track = document.createElement("div");
      track.className = "week-track tt-track";
      track.dataset.weekday = weekday;
      state.free.filter(byDay(weekday)).forEach(function (free) {
        track.appendChild(freeElement(free));
      });
      state.lectures.filter(byDay(weekday)).forEach(function (lecture) {
        track.appendChild(blockElement(lecture));
      });
      shifts.filter(byDay(weekday)).forEach(function (shift) {
        track.appendChild(shiftElement(shift));
      });
      day.appendChild(track);
      week.appendChild(day);
    }

    if (focusId !== undefined) {
      var block = week.querySelector('[data-id="' + focusId + '"]');
      if (block) block.focus();
    }
  }

  function byDay(weekday) {
    return function (item) { return item.weekday === weekday; };
  }

  function place(element, start, end) {
    element.style.top = percent(start) + "%";
    element.style.height = percent(end) - percent(start) + "%";
  }

  function freeElement(free) {
    var element = document.createElement("div");
    element.className = "tt-free";
    element.setAttribute("aria-hidden", "true");
    element.textContent = "frei";
    place(element, free.start, free.end);
    return element;
  }

  function blockElement(lecture) {
    var block = document.createElement("div");
    block.className = "week-block week-lecture tt-block";
    block.tabIndex = 0;
    block.setAttribute("role", "button");
    block.dataset.id = lecture.id;
    block.setAttribute("aria-label", lecture.title + ", " + DAY_NAMES[lecture.weekday] + " " +
      label(lecture.start, lecture.end) + ". Pfeiltasten verschieben, Umschalt und Pfeil ändert die Länge, Entf löscht.");
    var title = document.createElement("strong");
    title.textContent = lecture.title;
    var time = document.createElement("span");
    time.className = "tt-time";
    time.textContent = label(lecture.start, lecture.end);
    var handle = document.createElement("span");
    handle.className = "tt-resize";
    handle.setAttribute("aria-hidden", "true");
    block.appendChild(title);
    block.appendChild(time);
    block.appendChild(handle);
    place(block, lecture.start, lecture.end);
    // Überschneidungen nebeneinander und rot umrandet (#135). Die Spalten rechnet der Server
    // und schickt sie nach jeder Änderung mit; ein neuer Termin steht bis dahin in voller Breite.
    var layout = state.layout[lecture.id];
    if (layout) {
      block.style.setProperty("--left", layout.left + "%");
      block.style.setProperty("--width", layout.width + "%");
      if (layout.overlaps.length) {
        var hint = "Überschneidet sich mit " + layout.overlaps.join(", ");
        block.classList.add("tt-overlap");
        block.title = hint;
        block.setAttribute("aria-label", block.getAttribute("aria-label") + " " + hint + ".");
      }
    }
    return block;
  }

  // Eigene Schicht (#140): Link zur Stelle, nicht ziehbar. Konflikte rot mit Text.
  function shiftElement(shift) {
    var block = document.createElement("a");
    block.className = "week-block tt-job " + (shift.conflict ? "week-conflict tt-job-conflict" : "week-shift");
    block.href = shift.url;
    var text = shift.title + " (" + shift.company + "), " + DAY_NAMES[shift.weekday] + " " +
      label(shift.start, shift.end) + (shift.conflict ? ", " + shift.conflict : "");
    block.setAttribute("aria-label", text);
    block.title = text;
    var title = document.createElement("strong");
    title.textContent = shift.title;
    // Firmenlogo (#149) oder Initialen vor dem Titel, wie im Jobs-Listing
    var logo;
    if (shift.logoUrl) {
      logo = document.createElement("img");
      logo.className = "company-logo company-logo-small";
      logo.src = shift.logoUrl;
      logo.alt = "";
    } else {
      logo = document.createElement("span");
      logo.className = "company-logo company-logo-small company-logo-initials";
      logo.setAttribute("aria-hidden", "true");
      logo.textContent = shift.initials;
    }
    title.insertBefore(logo, title.firstChild);
    var time = document.createElement("span");
    time.textContent = label(shift.start, shift.end);
    block.appendChild(title);
    block.appendChild(time);
    if (shift.conflict) {
      var conflict = document.createElement("span");
      conflict.textContent = shift.conflict;
      block.appendChild(conflict);
    }
    place(block, shift.start, shift.end);
    return block;
  }

  function findLecture(id) {
    return state.lectures.filter(function (lecture) { return lecture.id === id; })[0];
  }

  // --- Speichern ------------------------------------------------------------

  function say(text) {
    statusLine.textContent = text;
  }

  function post(url, lecture) {
    var body = new FormData();
    if (lecture) {
      body.append("title", lecture.title);
      body.append("weekday", lecture.weekday);
      body.append("start", toText(lecture.start));
      body.append("end", toText(lecture.end));
    }
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
      body: body,
      credentials: "same-origin",
    }).then(function (response) {
      return response.json().then(function (json) {
        if (!response.ok) throw json;
        return json;
      });
    });
  }

  function idUrl(template, id) {
    return template.replace("/0/", "/" + id + "/");
  }

  function firstError(json) {
    var errors = (json && json.errors) || {};
    for (var field in errors) return errors[field][0];
    return "Speichern hat nicht geklappt. Bitte lade die Seite neu.";
  }

  // Nach jeder Antwort: Termin übernehmen, freie Blöcke, Stunden und Spalten neu zeichnen.
  function applyResponse(json) {
    state.free = json.free.map(fromJson);
    state.layout = json.layout;
    freeHours.textContent = json.free_hours.toLocaleString("de-DE", { maximumFractionDigits: 1 }) + " h";
  }

  function save(lecture, previous) {
    var isNew = lecture.id === undefined;
    var url = isNew ? urls.create : idUrl(urls.update, lecture.id);
    say("Speichert …");
    return enqueue(function () { return post(url, lecture); }).then(function (json) {
      var saved = fromJson(json.lecture);
      if (isNew) {
        state.lectures.push(saved);
      } else if (state.lectures.indexOf(lecture) !== -1) {
        // Nur übernehmen, wenn der Termin inzwischen nicht schon wieder geändert wurde
        state.lectures[state.lectures.indexOf(lecture)] = saved;
      }
      applyResponse(json);
      render(document.activeElement && document.activeElement.dataset.id ? saved.id : undefined);
      say(saved.title + " gespeichert.");
      return saved;
    }).catch(function (json) {
      // Zurück zum letzten gespeicherten Stand
      if (previous && state.lectures.indexOf(lecture) !== -1) {
        state.lectures[state.lectures.indexOf(lecture)] = previous;
      }
      render();
      say(firstError(json));
      throw json;
    });
  }

  // Speichern nacheinander, damit beim schnellen Tippen die letzte Änderung auch zuletzt ankommt.
  var queue = Promise.resolve();

  function enqueue(task) {
    var result = queue.then(task);
    queue = result.catch(function () {});
    return result;
  }

  function remove(lecture) {
    say("Löscht …");
    return enqueue(function () { return post(idUrl(urls.delete, lecture.id)); }).then(function (json) {
      state.lectures = state.lectures.filter(function (item) { return item.id !== lecture.id; });
      applyResponse(json);
      render();
      say(lecture.title + " gelöscht.");
    }).catch(function (json) { say(firstError(json)); });
  }

  // Änderung an einem bestehenden Termin: sofort zeichnen, dann speichern
  function change(lecture, changes) {
    var updated = Object.assign({}, lecture, changes);
    if (updated.start === lecture.start && updated.end === lecture.end &&
        updated.weekday === lecture.weekday && updated.title === lecture.title) return;
    state.lectures[state.lectures.indexOf(lecture)] = updated;
    render(updated.id);
    save(updated, lecture).catch(function () {});
  }

  // --- Popover: Titel ändern, löschen, neuen Termin benennen ----------------

  var popover = document.createElement("div");
  popover.className = "tt-popover";
  popover.setAttribute("role", "dialog");
  popover.setAttribute("aria-label", "Termin");
  popover.hidden = true;
  popover.innerHTML =
    '<form class="form">' +
    '  <label>Titel <input type="text" name="title" maxlength="100" required autocomplete="off"></label>' +
    '  <p class="tt-popover-time muted"></p>' +
    '  <p class="tt-popover-error" role="alert"></p>' +
    '  <div class="tt-popover-actions">' +
    '    <button type="submit" class="button button-primary">Speichern</button>' +
    '    <button type="button" class="button" data-delete>Löschen</button>' +
    '    <button type="button" class="button" data-close>Abbrechen</button>' +
    "  </div>" +
    "</form>";
  editor.appendChild(popover);
  var popoverForm = popover.querySelector("form");
  var popoverInput = popover.querySelector("input");
  var popoverLecture = null; // Termin im Popover; ohne id ist er neu und noch nicht gespeichert

  function openPopover(lecture, element) {
    popoverLecture = lecture;
    popoverInput.value = lecture.title;
    popover.querySelector(".tt-popover-time").textContent =
      DAY_NAMES[lecture.weekday] + ", " + label(lecture.start, lecture.end);
    popover.querySelector(".tt-popover-error").textContent = "";
    popover.querySelector("[data-delete]").hidden = lecture.id === undefined;
    popover.hidden = false;

    // Unter den Termin legen, aber innerhalb des Rasters bleiben
    var box = editor.getBoundingClientRect();
    var rect = element.getBoundingClientRect();
    var width = popover.offsetWidth;
    popover.style.left = clamp(rect.left - box.left, 8, box.width - width - 8) + "px";
    popover.style.top = rect.bottom - box.top + 6 + "px";
    popoverInput.focus();
    popoverInput.select();
  }

  function closePopover() {
    var lecture = popoverLecture;
    popover.hidden = true;
    popoverLecture = null;
    if (lecture && lecture.id === undefined) {
      render(); // neuer Termin ohne Titel: verwerfen
    } else if (lecture) {
      render(lecture.id);
    }
  }

  popoverForm.addEventListener("submit", function (event) {
    event.preventDefault();
    var title = popoverInput.value.trim();
    if (!title) {
      popover.querySelector(".tt-popover-error").textContent = "Bitte gib einen Titel ein.";
      return;
    }
    var lecture = popoverLecture;
    if (lecture.id === undefined) {
      lecture.title = title;
      save(lecture).then(function (saved) {
        popoverLecture = null;
        popover.hidden = true;
        render(saved.id);
      }).catch(function (json) {
        popover.querySelector(".tt-popover-error").textContent = firstError(json);
      });
    } else {
      popover.hidden = true;
      popoverLecture = null;
      change(lecture, { title: title });
    }
  });

  popover.querySelector("[data-delete]").addEventListener("click", function () {
    var lecture = popoverLecture;
    popover.hidden = true;
    popoverLecture = null;
    remove(lecture);
  });

  popover.querySelector("[data-close]").addEventListener("click", closePopover);

  popover.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closePopover();
  });

  // Klick daneben schließt das Popover und macht sonst nichts (wie im Kalender).
  document.addEventListener("pointerdown", function (event) {
    if (!popover.hidden && !popover.contains(event.target)) {
      event.stopPropagation();
      event.preventDefault();
      closePopover();
    }
  }, true);

  // --- Ziehen: anlegen, verschieben, Länge ändern ---------------------------

  var drag = null;

  week.addEventListener("pointerdown", function (event) {
    if (event.button !== 0) return;
    if (event.target.closest(".tt-job")) return; // Schicht: Link zur Stelle, kein neuer Termin
    var track = event.target.closest(".tt-track");
    if (!track) return;
    var block = event.target.closest(".tt-block");
    var weekday = Number(track.dataset.weekday);

    if (block) {
      var lecture = findLecture(Number(block.dataset.id));
      drag = {
        mode: event.target.classList.contains("tt-resize") ? "resize" : "move",
        lecture: lecture,
        element: block,
        startY: event.clientY,
        startX: event.clientX,
        moved: false,
        // Wo im Termin angefasst wurde, damit er beim Verschieben nicht springt
        offset: minutesAt(track, event.clientY) - lecture.start,
        result: { weekday: lecture.weekday, start: lecture.start, end: lecture.end },
      };
      capture(block, event.pointerId);
      block.focus();
      event.preventDefault();
    } else if (event.pointerType === "touch") {
      // Auf dem Handy scrollt Ziehen die Seite. Ein Tippen legt deshalb 90 Minuten an.
      drag = { mode: "tap", track: track, weekday: weekday, startY: event.clientY, startX: event.clientX, moved: false };
    } else {
      var anchor = minutesAt(track, event.clientY);
      var element = blockElement({ id: "neu", title: "Neuer Termin", weekday: weekday, start: anchor, end: anchor + STEP });
      element.classList.add("tt-new");
      track.appendChild(element);
      drag = { mode: "create", track: track, weekday: weekday, anchor: anchor, element: element,
        startY: event.clientY, startX: event.clientX, moved: false,
        result: { weekday: weekday, start: anchor, end: anchor + STEP } };
      capture(track, event.pointerId);
      event.preventDefault();
    }
  });

  window.addEventListener("pointermove", function (event) {
    if (!drag) return;
    if (Math.abs(event.clientY - drag.startY) + Math.abs(event.clientX - drag.startX) > DRAG_THRESHOLD) {
      drag.moved = true;
    }
    if (!drag.moved || drag.mode === "tap") return;

    var result = drag.result;
    if (drag.mode === "create") {
      var at = minutesAt(drag.track, event.clientY);
      result.start = Math.min(drag.anchor, at);
      result.end = Math.max(drag.anchor + STEP, at);
    } else if (drag.mode === "resize") {
      var track = week.querySelector('.tt-track[data-weekday="' + drag.lecture.weekday + '"]');
      result.end = clamp(minutesAt(track, event.clientY), drag.lecture.start + STEP, DAY_END);
    } else {
      var target = trackAt(event.clientX) || drag.element.parentNode;
      var duration = drag.lecture.end - drag.lecture.start;
      result.weekday = Number(target.dataset.weekday);
      result.start = clamp(minutesAt(target, event.clientY) - drag.offset, DAY_START, DAY_END - duration);
      result.end = result.start + duration;
      if (target !== drag.element.parentNode) target.appendChild(drag.element);
      drag.element.classList.add("tt-dragging");
    }
    place(drag.element, result.start, result.end);
    drag.element.querySelector(".tt-time").textContent = label(result.start, result.end);
  });

  window.addEventListener("pointerup", function (event) {
    if (!drag) return;
    var current = drag;
    drag = null;

    if (current.mode === "tap") {
      if (current.moved) return;
      var start = minutesAt(current.track, event.clientY);
      start = clamp(start, DAY_START, DAY_END - NEW_DURATION);
      startNew(current.track, current.weekday, start, start + NEW_DURATION);
    } else if (current.mode === "create") {
      var result = current.result;
      if (!current.moved) result.end = Math.min(result.start + NEW_DURATION, DAY_END);
      current.element.remove();
      startNew(current.track, current.weekday, result.start, result.end);
    } else if (!current.moved) {
      openPopover(current.lecture, current.element); // Klick ohne Ziehen
    } else {
      change(current.lecture, current.result);
    }
  });

  window.addEventListener("pointercancel", function () {
    // Zum Beispiel, wenn der Browser doch scrollt: nichts ändern
    if (!drag) return;
    if (drag.mode === "create") drag.element.remove();
    drag = null;
    render();
  });

  // Zeiger festhalten, damit Ziehen auch außerhalb des Termins weiterläuft. Die Listener
  // hängen am window, deshalb ist es nicht schlimm, wenn der Browser das ablehnt.
  function capture(element, pointerId) {
    try {
      element.setPointerCapture(pointerId);
    } catch (error) {
      // z. B. bei einem Zeiger, der schon wieder weg ist
    }
  }

  function startNew(track, weekday, start, end) {
    var lecture = { title: "", weekday: weekday, start: start, end: end };
    var element = blockElement({ id: "neu", title: "Neuer Termin", weekday: weekday, start: start, end: end });
    element.classList.add("tt-new");
    track.appendChild(element);
    openPopover(lecture, element);
  }

  // --- Tastatur -------------------------------------------------------------

  week.addEventListener("keydown", function (event) {
    var block = event.target.closest(".tt-block");
    if (!block || block.classList.contains("tt-new")) return;
    var lecture = findLecture(Number(block.dataset.id));
    var duration = lecture.end - lecture.start;
    var changes = null;

    if (event.key === "Enter" || event.key === " ") {
      openPopover(lecture, block);
    } else if (event.key === "Delete" || event.key === "Backspace") {
      remove(lecture);
    } else if (event.key === "ArrowUp" && event.shiftKey) {
      changes = { end: Math.max(lecture.end - STEP, lecture.start + STEP) };
    } else if (event.key === "ArrowDown" && event.shiftKey) {
      changes = { end: Math.min(lecture.end + STEP, DAY_END) };
    } else if (event.key === "ArrowUp") {
      var up = Math.max(lecture.start - STEP, DAY_START);
      changes = { start: up, end: up + duration };
    } else if (event.key === "ArrowDown") {
      var down = Math.min(lecture.start + STEP, DAY_END - duration);
      changes = { start: down, end: down + duration };
    } else if (event.key === "ArrowLeft") {
      changes = { weekday: Math.max(lecture.weekday - 1, 0) };
    } else if (event.key === "ArrowRight") {
      changes = { weekday: Math.min(lecture.weekday + 1, 4) };
    } else {
      return;
    }
    event.preventDefault();
    if (changes) change(lecture, changes);
  });

  render();
})();
