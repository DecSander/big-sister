var all_data = null;
var current_room = null;

function formatTime(time) {
  // Make a fuzzy time
  var date = new Date(time * 1000);
  var delta = Math.round((+new Date - date) / 1000);

  var minute = 60,
      hour = minute * 60,
      day = hour * 24,
      week = day * 7;

  var fuzzy;
  if (delta < minute) {
    fuzzy = delta + ' seconds ago';
  } else if (delta < 2 * minute) {
    fuzzy = 'a minute ago'
  } else if (delta < hour) {
    fuzzy = Math.floor(delta / minute) + ' minutes ago';
  } else if (Math.floor(delta / hour) == 1) {
    fuzzy = '1 hour ago.'
  } else if (delta < day) {
    fuzzy = Math.floor(delta / hour) + ' hours ago';
  } else if (delta < day * 2) {
    fuzzy = 'yesterday';
  } else {
    fuzzy = date.toString().slice(3, -15);
    var before = fuzzy.split(" ").slice(0, 4).join(' ') + ' ';
    var hr = (parseInt(fuzzy.split(" ")[4].split(":")[0]) + 12) % 12;
    var after = ':' + fuzzy.split(" ")[4].split(':').slice(1).join(':') + ' ';
    var ampm = parseInt(fuzzy.split(" ")[4].split(":")[0]) > 12 ? 'PM' : 'AM';
    fuzzy = before + String(hr) + after + ampm;
  }
  return fuzzy;
}

function handleSingleRoom(room_id, room) {
  $('#preloader').hide();
  $('#room-id').text('Room ' + room_id);
  $('#room-count').text('Occupancy: ' + room.camera_count);
  $('#room-time').text(formatTime(room.photo_time));
  $('#people-names').text('People: ', room.sightings.join(', '))
}

function handleAllCounts(data, setValues) {
  if (setValues === true) {
    var first_room = Object.keys(data)[0];
    $('#room-id').text(first_room);
    $('#room-count').text(data[first_room].camera_count);
    $('#people-names').text(data[first_room].sightings.join(', '));
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
      success: function(data) {
        handleSingleRoom(room_id, data);
      },
      error: console.error
    });
  } else {
    handleSingleRoom(room_id, all_data[room_id]);
  }
}

function createDropdown(data) {
  var optionString = data.map(function(key) {
    return '<li class="teal lighten-2 orange-text" onClick="getNewRoom(' + key + ')""><a href="#!">' + key + '</a></li>';
  }).join('');
  $('#dropdown1').html(optionString);

  $('#room-selector').dropdown({
    inDuration: 300,
    outDuration: 225,
    hover: false, // Activate on hover
    alignment: 'left', // Displays dropdown with edge aligned to the left of button
  });
}

function refresh() {
  $('#preloader').show();
  $('#room-id').text('');
  $('#room-count').text('');
  $('#room-time').text('');
  $('#people-names').text('');
  $.ajax({
    url: '/counts',
    type: 'GET',
    success: function(data) {
      all_data = data;
      if (Object.keys(all_data).length !== 0 && current_room === null) {
        current_room = Object.keys(all_data)[0];
        localStorage['current_room'] = current_room;
      }
      if (current_room !== null) handleSingleRoom(current_room, all_data[current_room])
      handleAllCounts(data);
    },
    error: console.error
  });
}

function getPrediction() {
  var date_selected = $('#date').val();
  var time_selected = $('#time').val();
  var epoch_selected = new Date(date_selected + ' ' + time_selected);
  $.ajax({
    url: '/counts/' + String(current_room) + '/' + String(epoch_selected.getTime() / 1000),
    type: 'GET',
    success: function(data) {
      var date_string = epoch_selected.getTime() > Date.now() ? 'Expected Occupancy: ' : 'Past Occupancy: ';
      if (data != null) $('#prediction').text(date_string + String(Math.round(data)));
      else $('#prediction').text('No Data Available');
    },
    error: console.error
  });
}


$(document).ready(function() {
  $('#date').datepicker();
  $('#time').timepicker();

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

function checkLoginState() {
  FB.getLoginStatus(function(response) {
    if (response.status === 'connected') {
      $('#fb-button').hide();
      $.ajax({
        url: '/fb_login',
        type: 'POST',
        contentType: 'application/json',
        body: JSON.stringify({auth: response.authResponse.accessToken})
      });
    }
  });
}

function changeGetButton() {
  var date_selected = $('#date').val();
  var time_selected = $('#time').val();
  if (date_selected === '' || time_selected === '') return;

  var epoch_selected = new Date(date_selected + ' ' + time_selected);
  if (epoch_selected.getTime() > Date.now()) $('#predict').text('Get Prediction');
  else $('#predict').text('Get Past');
}

if (!checkedLoginStatus && typeof FB !== 'undefined') {
  checkedLoginStatus = true;
  checkLoginState();
}
