// This file is part of Moodle - https://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <https://www.gnu.org/licenses/>.

/**
 * Proctoring flag badges on the quiz attempt review page, for reviewers.
 *
 * @module     quizaccess_examproctor/badges
 * @copyright  2026 Open University of Kenya
 * @license    https://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

const link = (text, url, cls) => {
    const a = document.createElement('a');
    a.className = cls;
    a.href = url;
    a.textContent = text;
    return a;
};

/**
 * Add a summary line above the questions and a badge on each flagged question.
 *
 * @param {Object} config
 * @param {Object<string, number>} config.counts flags per question element id.
 * @param {string} config.url proctoring report link for this session.
 * @param {string} config.band integrity band.
 * @param {string} config.label badge text, {$a} is the count.
 * @param {string} config.summary summary line text.
 */
export const init = ({counts, url, band, label, summary}) => {
    const first = document.querySelector('.que');
    if (first) {
        const cls = band === 'high' ? 'alert alert-danger' : (band === 'review' ? 'alert alert-warning' : 'alert alert-info');
        const box = document.createElement('div');
        box.className = cls;
        box.append(link(summary, url, 'alert-link'));
        first.parentNode.insertBefore(box, first);
    }
    Object.entries(counts).forEach(([elementid, count]) => {
        const info = document.getElementById(elementid)?.querySelector('.info');
        if (info) {
            info.append(link(label.replace('{$a}', count), url, 'badge bg-warning text-dark d-inline-block mt-2'));
        }
    });
};
