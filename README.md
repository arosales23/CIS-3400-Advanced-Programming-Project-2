# Band Inventory & Equipment Tracking
A web app that lets band directors track instruments, uniforms, and equipment, and who has which item

## <b>Project Overview</b>

### Application Name: [Name]
**This project is a <b>database-driven web application</b>

### Problem to Solve:
Band directors and other equipment managers may struggle to keep track of all equipment. For example, one student may have checked out multiple instruments or may be using multiple pieces of equipment. Another scenario is that one uniform has separate parts (i.e., jacket, pants, and cape) assigned numbers (such as 101, 178, 222, etc., that correspond to sizes), but one student may have a jacket from one uniform and pants from another. Having one place to be able to track everything would be very convenient for the person in charge.

### Intended Users:
Band directors, staff, or student leaders who need to review inventory to add new equipment or disregard old equipment, and see who has what equipment.

### Planned Features:
Track inventory of instruments, equipment, uniforms, and folders <br>
Track the conditions of inventory (i.e., Excellent, Great, Good, Poor) <br>
Track the qualities of [maybe just instruments and some equipment] (i.e., Professional, Intermediate, Beginner) <br>

### Planned Technologies:
<table>
  <thead>
    <tr>
      <th scope="col">Technology</th>
      <th scope="col">Purpose</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Python</td>
      <td>Main programming language</td>
    </tr>
    <tr>
      <td>Flask/Streamlit</td>
      <td>Web interface and application framework</td>
    </tr>
    <tr>
      <td>SQLite / MongoDB</td>
      <td>Data Storage</td>
    </tr>
  </tbody>
</table>

### Data/Model Plan:
Student: ID, Name, Email <br>
Staff: ID, Name (of Director, Assistants, or Student Leaders) <br>
Instrument: ID, Name (Flute, Bass Clarinet, Baritone Saxophone, String Bass, etc.), Condition, Quality, Status <br>
Equipment: ID, Name (Mutes, Mics, Drum Sticks, Mallets), Checkout ID <br>

Folder: ID, Number, Student ID <b>(No Checkout because students pick them up themselves, and they are expected to return them within a timeframe)</b> <br>

Checkout: Item ID, Student ID, Date Checked Out, Date Checked In, Checked Out By, Checked In By <br>
Uniform: Shako (hat) Size (S, M, L, XL, XXL, XXXL), Jacket Number, Bibber (pants) Number, Gauntlet Size <br>

[On Checked Out/In By, add dropdown menu]

### Preliminary Interface Sketch


### Anticipated Challenges:
Modeling uniforms as separate parts, since most students have mismatched numbers.
