import sys
import os
# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from niDAQ import NIDAQReader, NIDAQSettings

# Example usage (commented):
if __name__ == "__main__":
    settings = NIDAQSettings(device_name="Dev1", 
                             channels=["ai0", "ai1"], 
                             sampling_rate_hz=20.0,
                             terminal_config="RSE",)
    reader = NIDAQReader(settings)
    reader.start()
    try:
        # Test 1 - read data 5 times and print 10 rows per iteration
        for _ in range(5):
            t, y = reader.read_data(number_of_samples_per_channel=200, average_ms=10)
            # t, y = reader.read_data(number_of_samples_per_channel=200, average_ms=10, rolling_avg=False)
            # t, y = reader.read_data(number_of_samples_per_channel=100)
            reader.print_data(max_rows=10)
        
        # Test 2 - read data and plot
        reader.read_data(number_of_samples_per_channel=1000)
        reader.plot_data()  # all channels, shared y from v_min/v_max
        # reader.plot_data(auto_ylim=True)                 # all channels, auto y
        # reader.plot_data(channels=["ai0"], auto_ylim=True)
        # reader.plot_data(channels=["ai0","ai1"], separate=True, auto_ylim=True, show_mean=True)
        
        # Test 3 - plot realtime data   
        reader.plot_realtime(
            interval_ms=50,
            window_ms=4000,
            channels=["ai0","ai1"],
            separate=False,
            auto_ylim=True,
            rolling_avg_ms=None,
            rolling_avg=False,
            show_mean=False
        )
    finally:
        # Save data and close the reader
        reader.save_data("run.csv")
        # reader.print_data(max_rows=10)
        reader.close()
