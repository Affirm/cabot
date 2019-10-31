// arrow functions are pretty, screw IE 11

// load value string into e
function runwindow_load(value, e) {
    console.log("loading: " + e.value);
    var data = value && JSON.parse(value);
    var useSchedule = !!data;

    root = $(e).parent();
    root.find('[name=' + e.name + '-start], [name=' + e.name + '-end], [name^=' + e.name + '-day-]')
        .add(root.find('[name^=' + e.name + '-day-]').parent())
        .attr('disabled', useSchedule ? null : 'true');
    root.find('input[name=' + e.name + '-use-schedule]').attr('checked', useSchedule ? 'checked' : null);

    if (!data)
        return;  // no data; default form state is good

    start_time = data[0]['start_time'];
    end_time = data[0]['end_time'];
    rrule = data[0]['rrule'];

    root.find('[name=' + e.name + '-start]').val(start_time);
    root.find('[name=' + e.name + '-end]').val(end_time);

    var enabledDays = /BYDAY=(([A-Z]{2},?)*)/.exec(rrule)[1].split(',');
    root.find('[name^=' + e.name + '-day-]').each((_, dow) => {
        var enable = enabledDays.includes(dow.name.split('-')[2]);
        $(dow).attr('checked', enable ? 'checked' : null);
        if (enable)
            $(dow).parent().addClass('active');
        else
            $(dow).parent().removeClass('active');
    });
}

// serialize values for e's inputs into e.value (which gets submitted with the form)
function runwindow_save(e) {
    root = $(e).parent();
    var useSchedule = root.find('input[name=' + e.name + '-use-schedule]').is(':checked');
    // these are 'HH:MM' or empty string
    var startTime = root.find('input[name=' + e.name + '-start]').val();
    var endTime = root.find('input[name=' + e.name + '-end]').val();
    // ['MO', 'TU', ...] etc. of checked months
    var daysOfWeek = root.find('input[name^=' + e.name + '-day-]:checked').map((_, dow) => dow.name.split('-')[2]).get();

    // set scheduling stuff as disabled if useSchedule is false
    root.find('[name=' + e.name + '-start], [name=' + e.name + '-end], [name^=' + e.name + '-day-]').add(root.find('[name^=' + e.name + '-day-]').parent())
        .attr('disabled', useSchedule ? null : 'true');
    if (!useSchedule) {
        e.value = '';
        console.log('[no schedule]');
    } else {
        var val = [{
            'start_time': startTime,
            'end_time': endTime,
            'rrule': 'FREQ=WEEKLY;INTERVAL=1;BYDAY=' + daysOfWeek.join(','),
        }];
        console.log(val);
        e.value = JSON.stringify(val);
    }
}

$(document).ready(() => {
    $('.runwindow-form').each((_, e) => {
        // load hidden field data into the UI
        runwindow_load(e.value, e);

        // when any relevant controls are changed, recalculate e.value
        $(e).parent().find('[name^=' + e.name + ']').change((_) => runwindow_save(e));
    });
});