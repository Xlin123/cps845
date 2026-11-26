# User stories: CM — membership management for a recreational club

## Use case points

- 3 complex actors
- Actor sum = (3 \* 3) = 9
- Use case sum, using the numbers below:
  - = 2 simple \* 4 average \* 2 complex
  - = (2 \* 5) + (4 \* 10) + (2 \* 15) = 80
- UUCP = Actor sum + UCS = 80 + 9 = 89

## Project backlog

### Create Profile

| Field | Value |
|---|---|
| Actor | Customer, Coach |
| Description | The process in which the user enters his/her name, email address, phone number and password into the system to create a user profile. |
| Normal Course | 1. The use case is initiated when the user chooses the create a profile option in the application menu.<br>2. The user enters their name into the system.<br>3. The user enters a valid email address, phone number and password.<br>4. A confirmation email is sent to the user's email address.<br>5. Profile is activated when link in confirmation email is confirmed. |
| Alternative Course | 3a. If the user enters an improperly formatted email address, an error message appears.<br>3b. If the user enters an invalid password, an error message appears.<br>5b. Link is never followed, profile info deleted after 4 days. |
| Preconditions | App exists, user has an email address. |
| Post-conditions | The application adds the user profile to the database. |
| Assumptions | — |
| Use Case Complexity | 8 |

### Check Unpaid Sessions

| Field | Value |
|---|---|
| Actor | Customer |
| Description | The process in which the user checks his/her unpaid sessions and is able to view his/her total amount of owed money. |
| Normal Course | 1. The use case is initiated when the user chooses the unpaid sessions option in the application menu.<br>2. A summary of dated unpaid sessions, cost per class, and total money owed is displayed to the user. |
| Alternative Course | 1a. If the user does not have any unpaid sessions, a message appears stating this, returns user to application menu. |
| Preconditions | User has a profile. |
| Post-conditions | A summary of unpaid sessions is displayed to the user. |
| Assumptions | — |
| Use Case Complexity | 3 |

### Check In

| Field | Value |
|---|---|
| Actor | Customer, Coach |
| Description | The process in which the user signals they have made it to a lesson. This increments their sessions attended number and records current date. |
| Normal Course | 1. The use case is initiated when the user clicks the button on the application menu. |
| Alternative Course | N/A |
| Preconditions | The app is functioning and user has a profile. |
| Post-conditions | The user's sessions attended is incremented by one and date is saved. |
| Assumptions | The user has a profile already. |
| Use Case Complexity | 1 |

### Session Created

| Field | Value |
|---|---|
| Actors | Coach |
| Brief Description | User selects a date for a future session. |
| Basic Flow | 1. Use case begins when user selects "Create Session" option.<br>2. The system prompts coach for a date and time.<br>3. The session is created and is added into the system's database.<br>4. System updates a queue of notifications to be sent out to club members and user is returned to main menu. |
| Alternative Flows | 1. The user selects cancel then the session creation operation ends.<br>2. The system detects a collision and re-prompts the user to either overwrite session or cancel operation. |
| Preconditions | A database for date checking exists. App exists. |
| Postconditions | At the end of the use case, the session(s) is created and the notification queue is updated. |
| Use Case Complexity | 6 |

### Session Deleted

| Field | Value |
|---|---|
| Actors | Coach |
| Brief Description | The user deletes a session. |
| Basic Flow | 1. Use case begins when user (the Coach) selects "Delete Session" option.<br>2. The system displays a table of existing sessions which can each be selected or deselected by the user.<br>3. User clicks delete button and is prompted by app with "Are you sure you want to delete these?" and lists all selected sessions.<br>4. All sessions selected are deleted and removed from system database.<br>5. System removes unnecessary notifications from its notification queue. |
| Alternative Flows | 1. The user selects cancel then the session creation operation ends.<br>3. User selects "No" and is returned to main menu. |
| Preconditions | A database for date checking exists. App exists. |
| Postconditions | At the end of the use case, the session(s) is deleted and the notification queue is updated. |
| Use Case Complexity | 7 |

### Club Finances

| Field | Value |
|---|---|
| Actor | Treasurer |
| Description | The process in which the Treasurer checks overall club finances as well as individual user information. Also allows the Treasurer to manipulate the total money in finances in order to simulate paying out coaches or rent. |
| Normal Course | 1. The use case is initiated when the treasurer logs into the app.<br>2. They are presented with the total finances accumulated by the club as well as two buttons (Button A and Button B).<br>3a. When pressed, button A will change the screen to show each individual profile and their current balance.<br>3b. There exists an exit button to return to the previous screen.<br>4a. When button B is pressed it will bring up an option for the user to lower the total funds of the club to simulate the user paying rent or their coaches.<br>4b. There exists an exit button to return to the previous screen. |
| Alternative Course | 3a. If there are no users then a message will pop up stating as such and putting them back at the previous screen.<br>4a. If the funds are lowered below the amount of money the club has, an error message will occur and no change of funds will be done. |
| Preconditions | The app exists. |
| Post-conditions | The total funds may be changed afterwards. |
| Assumptions | — |
| Use Case Complexity | 8 |

### Sessions Not Paid

| Field | Value |
|---|---|
| Actor | Treasurer |
| Description | The process whereby the treasurer notifies the customer regarding any missed session payments. |
| Normal Course | 1. They are presented with a list of all customer profiles with outstanding payments and two buttons (Button A and Button B).<br>&nbsp;&nbsp;a. When button A is pressed, a batch email is sent to the emails associated with each customer's profile. Each email includes the individual customer's amount owed.<br>&nbsp;&nbsp;b. When button B is pressed, the user is returned to the previous screen. |
| Alternative Course | 1. There exist no customers with outstanding payments and an error message will pop up with this message as a result.<br>&nbsp;&nbsp;a. The use case ends and the user is returned to the initial notification selection panel. |
| Preconditions | "Send warning for unpaid sessions" option is selected by the treasurer in main application menu. |
| Post-conditions | An email is sent to customers through the e-mail address designated on their respective profiles. |
| Assumptions | Assumes that all customers are registered and have created a valid profile on the system. |
| Use Case Complexity | 5 |

### Notify Members

| Field | Value |
|---|---|
| Actor | Treasurer, Coach |
| Description | The process whereby the treasurer or the coach notifies the customers. |
| Normal Course | 1. The use case is initiated when the user selects one of the three following options from a main menu:<br>&nbsp;&nbsp;a. Send email warnings about sessions unpaid for (Treasurer).<br>&nbsp;&nbsp;b. Send email notifications about sessions created (Coach).<br>&nbsp;&nbsp;c. Send email notifications about sessions deleted (Coach).<br>2. Once an option has been selected, the system grabs relevant user information based on the selection and directs the user to the appropriate includes use case. |
| Alternative Course | 2. The user has selected an option that they do not have permission to access.<br>&nbsp;&nbsp;a. An error message will pop up stating that the user does not have permission to access such functionality.<br>&nbsp;&nbsp;b. The user is re-prompted to select another option. |
| Preconditions | The app exists, the user has logged in. |
| Post-conditions | An email is sent out to the customers through their respective e-mail address listed on the profile with topics dependent on the option selected by the actors. |
| Assumptions | Assumes that all customers are registered and have created a valid profile on the system. |
| Use Case Complexity | 7 |
