var all_data = null;
var current_room = null;

function formatTime(time) {
  // Make a fuzzy time
  var date = new Date(time);
  var delta = Math.round((+new Date - date) / 1000);

  var minute = 60,
      hour = minute * 60,
      day = hour * 24,
      week = day * 7;

  var fuzzy;
  if (delta < 30) {
    fuzzy = 'just then.';
  } else if (delta < minute) {
    fuzzy = delta + ' seconds ago.';
  } else if (delta < 2 * minute) {
    fuzzy = 'a minute ago.'
  } else if (delta < hour) {
    fuzzy = Math.floor(delta / minute) + ' minutes ago.';
  } else if (Math.floor(delta / hour) == 1) {
    fuzzy = '1 hour ago.'
  } else if (delta < day) {
    fuzzy = Math.floor(delta / hour) + ' hours ago.';
  } else if (delta < day * 2) {
    fuzzy = 'yesterday';
  } else {
    fuzzy = date.toString().slice(3, -15);
  }
  return fuzzy;
}

function handleSingleRoom(room_id, room) {
  $('#room-id').text('Room ' + room_id);
  $('#room-count').text('Occupancy: ' + room.camera_count);
  $('#room-time').text(formatTime(room.photo_time));
}

function handleAllCounts(data, setValues) {
  if (setValues === true) {
    var first_room = Object.keys(data)[0];
    $('#room-id').text(first_room);
    $('#room-count').text(data[first_room].camera_count);
  }
  createDropdown(Object.keys(data));
}

function getNewRoom(room_id) {
  current_room = room_id;
  localStorage['room_id'] = room_id;

  if (all_data === null || !all_data.hasOwnProperty(room_id)) {
    $.ajax({
      url: '/counts/' + room_id,
      type: 'GET',
      success: function(data) { handleSingleRoom(room_id, data); },
      error: console.error
    });
  } else {
    handleSingleRoom(room_id, all_data[room_id]);
  }
}

function createDropdown(data) {
  var optionString = data.map(function(key) {
    return '<li className onClick="getNewRoom(' + key + ')"">' + key + '</li>';
  }).join('');
  $('#dropdown1').html(optionString);

  $('#room-selector').dropdown({
    inDuration: 300,
    outDuration: 225,
    hover: false, // Activate on hover
    gutter: 0, // Spacing from edge
    belowOrigin: false, // Displays dropdown below the button
    alignment: 'left', // Displays dropdown with edge aligned to the left of button
    stopPropagation: false // Stops event propagation
  });
}

function refresh() {
  $.ajax({
    url: '/counts',
    type: 'GET',
    success: function(data) {
      all_data = data;
      if (current_room !== null) handleSingleRoom(current_room, all_data[current_room]);
    },
    error: console.error
  });
}

$(document).ready(function() {
  if (localStorage.getItem('room_id') !== null) {
    var room_id = localStorage.getItem('room_id');
    getNewRoom(room_id);

    $.ajax({
      url: '/rooms',
      type: 'GET',
      success: function(data) {
        createDropdown(data);
        refresh();
      },
      error: console.error
    });
  } else {
    refresh();
  }
});