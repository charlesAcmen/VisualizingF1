# FastF1 Telemetry Explorer

A web application for visualizing Formula 1 telemetry data with multi-driver comparison capabilities. Built with React frontend and Python FastF1 backend.

## Features

- **Multi-driver telemetry comparison**: Compare lap data from multiple drivers simultaneously
- **Distance-based x-axis**: Accurate lap visualization with corner markers
- **Support for all F1 sessions**: Practice, Qualifying, Sprint, Race
- **Pre-season testing support**: Special handling for testing events with clear session naming
- **Real-time data fetching**: Direct integration with FastF1 API
- **Interactive charts**: Powered by Plotly.js for smooth zooming and panning
- **Team color integration**: Automatic driver team colors from official F1 data

## Prerequisites

- Python 3.8 or higher
- Node.js 16 or higher
- npm or yarn

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/charlesAcmen/VisualizingF1.git
cd VisualizingF1
```

### 2. Set Up Python Backend

#### Create and Activate Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

#### Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Frontend

```bash
npm install
```

## Usage

### 1. Start the Backend Server

In your activated virtual environment:

```bash
python api_server.py
```

The API server will start on `http://localhost:8000`

### 2. Start the Frontend Development Server

In a new terminal:

```bash
npm run dev
```

The frontend will start on `http://localhost:5173`

### 3. Access the Application

Open your browser and navigate to `http://localhost:5173`

## API Endpoints

- `GET /api/events?season={year}` - Get list of events for a season
- `GET /api/sessions?season={year}&event={event_name}` - Get sessions for an event
- `GET /api/drivers?season={year}&event={event_name}&session={session_code}` - Get drivers for a session
- `GET /api/laps?season={year}&event={event_name}&session={session_code}&driver={driver}` - Get lap numbers for a driver
- `GET /api/lap?season={year}&event={event_name}&session={session_code}&driver={driver}&lap={lap_number}` - Get telemetry data for a specific lap

## Session Codes

- `FP1`, `FP2`, `FP3` - Practice sessions
- `Q` - Qualifying
- `SQ` - Sprint Qualifying
- `S` - Sprint Race
- `SS` - Sprint Shootout
- `R` - Race
- `T{event_num}{session_num}` - Testing sessions (e.g., `T11`, `T12`, `T13`)

## Testing Events

Pre-season testing events are specially handled:
- Events display with official names (e.g., "Pre-Season Testing")
- Sessions are labeled as "Day 1", "Day 2", "Day 3" for clarity
- Session codes follow the `T{event_num}{session_num}` pattern

## Project Structure

```
├── api_server.py          # Python FastF1 backend
├── requirements.txt        # Python dependencies
├── src/
│   ├── App.tsx          # React main application
│   ├── main.tsx         # React entry point
│   └── styles.css       # Application styles
├── package.json          # Node.js dependencies
└── index.html           # HTML template
```

## Dependencies

### Python Backend
- `fastf1` - F1 data API
- `pandas` - Data manipulation

### Frontend
- `react` - UI framework
- `plotly.js-dist-min` - Charting library
- `typescript` - Type safety
- `vite` - Build tool

## Development

### Running in Development Mode

1. Start the backend server: `python api_server.py`
2. Start the frontend dev server: `npm run dev`
3. Open `http://localhost:5173`

### Building for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

## Troubleshooting

### Common Issues

1. **FastF1 Cache Issues**: Delete the `.fastf1_cache` directory and restart
2. **Port Conflicts**: Ensure ports 8000 and 5173 are available
3. **Virtual Environment**: Make sure the Python virtual environment is activated before installing dependencies

### Data Loading Tips

- First-time data loading may take several minutes as FastF1 downloads and caches data
- Testing events may have limited driver data compared to race weekends
- Some sessions may not have telemetry data available for all drivers

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is for educational purposes. Please respect the terms of service of the data sources used.

## Acknowledgments

- [FastF1](https://github.com/theOehrly/Fast-F1) - F1 data API
- [Plotly.js](https://plotly.com/javascript/) - Interactive charting
- [React](https://reactjs.org/) - UI framework
