const functions = require('firebase-functions');
const admin = require('firebase-admin');
const sendgrid = require('@sendgrid/mail');

// Initialize Firebase Admin
admin.initializeApp();

// Initialize SendGrid
sendgrid.setApiKey(functions.config().sendgrid.api_key);

exports.sendScheduleEmail = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError('unauthenticated', 'User must be authenticated.');
  }

  const scheduleId = data.scheduleId;
  if (!scheduleId) {
    throw new functions.https.HttpsError('invalid-argument', 'Schedule ID is required.');
  }

  try {
    const scheduleDoc = await admin.firestore()
      .collection('schedules')
      .doc(scheduleId)
      .get();

    if (!scheduleDoc.exists) {
      throw new functions.https.HttpsError('not-found', 'Schedule not found.');
    }

    const schedule = scheduleDoc.data();
    if (schedule.user_id !== context.auth.uid) {
      throw new functions.https.HttpsError('permission-denied', 'User not authorized to access this schedule.');
    }

    const venues = schedule.venues || [];
    const venueList = venues.map(v => 
      `- ${v.name || 'Your Location'} (${v.location.formattedAddress.join(', ')})`
    ).join('\n');

    const emailContent = `
      Your Smart City Traveller Schedule:
      City: ${schedule.city}
      Date: ${schedule.date}
      Time: ${schedule.start_time} - ${schedule.end_time}
      Interests: ${schedule.interests}
      Venues:
      ${venueList}
    `;

    const msg = {
      to: context.auth.token.email,
      from: 'your-verified-sender@example.com', // Replace with your verified sender email
      subject: 'Your Smart City Traveller Schedule',
      text: emailContent,
      html: `<pre>${emailContent}</pre>`,
    };

    await sendgrid.send(msg);
    return { success: true, message: 'Email sent successfully.' };
  } catch (error) {
    console.error('Error sending email:', error);
    throw new functions.https.HttpsError('internal', `Failed to send email: ${error.message}`);
  }
});