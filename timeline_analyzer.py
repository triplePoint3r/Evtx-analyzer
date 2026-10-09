"""
Timeline Analyzer Module
Merges multiple XML event logs into a single chronological timeline
"""

import heapq
import xml.etree.ElementTree as ET
import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Iterator


BASE_DIR = Path(__file__).parent
SAMPLES_DIR = BASE_DIR / "samples"
LOGS_DIR = BASE_DIR / "logs"
TIMELINE_DIR = BASE_DIR / "timelines"


class TimelineAnalyzer:
    """Analyzes and merges multiple event log files"""
    
    def __init__(self):
        self.namespace = {'evt': 'http://schemas.microsoft.com/win/2004/08/events/event'}
        TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    
    def sanitize_xml(self, xml_string: str) -> str:
        """Sanitize XML string by removing invalid characters"""
        import re
        xml_string = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x84\x86-\x9F]', '', xml_string)
        return xml_string
    
    def parse_event_xml(self, xml_string: str) -> Dict:
        """Parse event XML from python-evtx format"""
        try:
            # Sanitize XML first
            xml_string = self.sanitize_xml(xml_string)
            
            # Parse XML
            try:
                root = ET.fromstring(xml_string)
            except ET.ParseError as e:
                return None
            
            # Find the System element
            system = root.find('evt:System', self.namespace)
            if system is None:
                system = root.find('System')
            
            if system is None:
                return None
            
            # ===== Extract TimeCreated =====
            timestamp = None
            time_created = system.find('evt:TimeCreated', self.namespace)
            if time_created is None:
                time_created = system.find('TimeCreated')
            
            if time_created is not None:
                timestamp_str = time_created.get('SystemTime')
                if not timestamp_str and time_created.text:
                    timestamp_str = time_created.text.strip()
                
                if timestamp_str:
                    try:
                        if 'T' in timestamp_str:
                            if timestamp_str.endswith('Z'):
                                timestamp_str = timestamp_str.replace('Z', '+00:00')
                            timestamp = datetime.fromisoformat(timestamp_str)
                        else:
                            timestamp = datetime.fromisoformat(timestamp_str)
                    except:
                        try:
                            timestamp_str_clean = timestamp_str.split('.')[0]
                            if '+' in timestamp_str_clean or timestamp_str_clean.endswith('Z'):
                                timestamp = datetime.fromisoformat(timestamp_str_clean.replace('Z', '+00:00'))
                            else:
                                timestamp = datetime.strptime(timestamp_str_clean, '%Y-%m-%d %H:%M:%S')
                        except:
                            timestamp = datetime.now()
            
            if timestamp is None:
                return None
            
            # ===== Remaining extractions =====
            event_id_elem = system.find('evt:EventID', self.namespace)
            if event_id_elem is None:
                event_id_elem = system.find('EventID')
            event_id = event_id_elem.text.strip() if event_id_elem is not None and event_id_elem.text else 'Unknown'
            
            channel_elem = system.find('evt:Channel', self.namespace)
            if channel_elem is None:
                channel_elem = system.find('Channel')
            channel = channel_elem.text.strip() if channel_elem is not None and channel_elem.text else 'Unknown'
            
            computer_elem = system.find('evt:Computer', self.namespace)
            if computer_elem is None:
                computer_elem = system.find('Computer')
            computer = computer_elem.text.strip() if computer_elem is not None and computer_elem.text else 'Unknown'
            
            provider_elem = system.find('evt:Provider', self.namespace)
            if provider_elem is None:
                provider_elem = system.find('Provider')
            provider_name = provider_elem.get('Name', 'Unknown') if provider_elem is not None else 'Unknown'
            
            record_id_elem = system.find('evt:EventRecordID', self.namespace)
            if record_id_elem is None:
                record_id_elem = system.find('EventRecordID')
            record_id = record_id_elem.text.strip() if record_id_elem is not None and record_id_elem.text else 'Unknown'
            
            level_elem = system.find('evt:Level', self.namespace)
            if level_elem is None:
                level_elem = system.find('Level')
            level = level_elem.text.strip() if level_elem is not None and level_elem.text else 'Unknown'
            
            level_map = {
                '0': 'Log Always', '1': 'Critical', '2': 'Error', 
                '3': 'Warning', '4': 'Information', '5': 'Verbose'
            }
            level_str = level_map.get(level, level)
            
            # ===== Extract User (Security context) =====
            user = 'N/A'
            # Check System/Security element for UserID (SID)
            security_elem = system.find('evt:Security', self.namespace)
            if security_elem is None:
                security_elem = system.find('Security')
            if security_elem is not None:
                uid = security_elem.get('UserID', '')
                if uid:
                    user = uid

            # Prefer a human-readable account name from EventData when available
            event_data = root.find('evt:EventData', self.namespace)
            if event_data is None:
                event_data = root.find('EventData')

            if event_data is not None:
                # Look for common username field names in priority order
                username_fields = ('SubjectUserName', 'TargetUserName', 'UserName', 'AccountName')
                for ns_prefix in ('evt:', ''):
                    tag = f'{ns_prefix}Data' if ns_prefix else 'Data'
                    ns = self.namespace if ns_prefix else {}
                    for data_elem in event_data.findall(tag, ns):
                        elem_name = data_elem.get('Name', '')
                        if elem_name in username_fields and data_elem.text:
                            candidate = data_elem.text.strip()
                            if candidate and candidate not in ('-', 'N/A'):
                                user = candidate
                                break
                    if user not in ('N/A', '') and not user.startswith('S-'):
                        break

            # ===== Extract Description from EventData =====
            description_parts = []
            if event_data is not None:
                for ns_prefix in ('evt:', ''):
                    tag = f'{ns_prefix}Data' if ns_prefix else 'Data'
                    ns = self.namespace if ns_prefix else {}
                    elems = event_data.findall(tag, ns)
                    if elems:
                        for data_elem in elems:
                            text = (data_elem.text or '').strip()
                            if not text:
                                continue
                            name = data_elem.get('Name', '')
                            description_parts.append(f"{name}={text}" if name else text)
                        break  # stop after first namespace match that produced results

            description = '; '.join(description_parts[:8])  # cap at 8 key-value pairs

            return {
                'timestamp': timestamp,
                'event_id': event_id,
                'channel': channel,
                'computer': computer,
                'provider': provider_name,
                'record_id': record_id,
                'level': level_str,
                'user': user,
                'description': description,
                'xml': xml_string
            }
            
        except Exception as e:
            return None
    
    def event_generator(self, xml_file: Path) -> Iterator[Dict]:
        """
        Generator to read events from XML file one at a time
        Reads an Event correctly even if it spans multiple lines
        """
        event_count = 0
        error_count = 0
        
        try:
            with open(xml_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Find all Events using regex
            import re
            
            # Search pattern: from <Event to </Event> (inclusive)
            pattern = r'<Event[^>]*>.*?</Event>'
            events = re.findall(pattern, content, re.DOTALL)
            
            for event_xml in events:
                # Try to parse
                parsed = self.parse_event_xml(event_xml)
                if parsed:
                    event_count += 1
                    yield parsed
                else:
                    error_count += 1
            
            # Print summary for this file
            print(f"  ✅ {xml_file.name}: {event_count} events parsed, {error_count} skipped")
                        
        except Exception as e:
            print(f"❌ Error reading {xml_file}: {e}")
    
    def merge_timelines(self, xml_files: List[Path]) -> Iterator[Dict]:
        """Merge multiple XML files into single chronological timeline"""
        file_generators = []
        for xml_file in xml_files:
            if xml_file.exists():
                gen = self.event_generator(xml_file)
                file_generators.append((xml_file, gen))
        
        heap = []
        
        for idx, (xml_file, gen) in enumerate(file_generators):
            try:
                event = next(gen)
                heapq.heappush(heap, (event['timestamp'], idx, event))
            except StopIteration:
                pass
        
        while heap:
            timestamp, file_idx, event = heapq.heappop(heap)
            yield event
            
            try:
                xml_file, gen = file_generators[file_idx]
                next_event = next(gen)
                heapq.heappush(heap, (next_event['timestamp'], file_idx, next_event))
            except StopIteration:
                pass
    
    def analyze_timeline(self, xml_files: List[Path], output_file: Path = None, 
                        filters: Dict = None, progress_callback=None):
        """Analyze timeline from multiple XML files and save results"""
        print(f"🔍 Starting timeline analysis...")
        print(f"📁 Files to analyze: {len(xml_files)}")
        
        events_count = 0
        matched_count = 0
        channels_stats = {}
        event_ids_stats = {}
        computers_stats = {}
        
        # Parse filters
        if filters:
            channels_filter = set(filters.get('channels', [])) if filters.get('channels') else None
            event_ids_filter = set(str(x) for x in filters.get('event_ids', [])) if filters.get('event_ids') else None
            computers_filter = set(filters.get('computers', [])) if filters.get('computers') else None
            
            start_time = None
            end_time = None
            if filters.get('start_time'):
                try:
                    start_time = datetime.fromisoformat(filters['start_time'])
                except:
                    start_time = None
                    
            if filters.get('end_time'):
                try:
                    end_time = datetime.fromisoformat(filters['end_time'])
                except:
                    end_time = None
        else:
            channels_filter = event_ids_filter = computers_filter = None
            start_time = end_time = None
        
        # Open output file
        csv_file = None
        csv_writer = None
        if output_file:
            csv_file = open(output_file, 'w', newline='', encoding='utf-8')
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                'Timestamp', 'Channel', 'EventID', 'Level',
                'Computer', 'Provider', 'RecordID', 'User', 'Description'
            ])
        
        # Process events
        for event in self.merge_timelines(xml_files):
            events_count += 1
            
            channel = event['channel']
            event_id = event['event_id']
            computer = event['computer']
            
            channels_stats[channel] = channels_stats.get(channel, 0) + 1
            event_ids_stats[event_id] = event_ids_stats.get(event_id, 0) + 1
            computers_stats[computer] = computers_stats.get(computer, 0) + 1
            
            # Apply filters
            if channels_filter and event['channel'] not in channels_filter:
                continue
            if event_ids_filter and event['event_id'] not in event_ids_filter:
                continue
            if computers_filter and event['computer'] not in computers_filter:
                continue
            if start_time and event['timestamp'] < start_time:
                continue
            if end_time and event['timestamp'] > end_time:
                continue
            
            matched_count += 1
            
            # Write to CSV
            if csv_writer:
                timestamp_str = event['timestamp'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                csv_writer.writerow([
                    timestamp_str,
                    event['channel'],
                    event['event_id'],
                    event['level'],
                    event['computer'],
                    event['provider'],
                    event['record_id'],
                    event.get('user', 'N/A'),
                    event.get('description', ''),
                ])
            
            # Progress callback
            if progress_callback and events_count % 1000 == 0:
                progress_callback(events_count, matched_count)
        
        if csv_file:
            csv_file.close()
        
        # Create statistics
        stats = {
            'total_events': events_count,
            'matched_events': matched_count,
            'channels': channels_stats,
            'event_ids': dict(sorted(event_ids_stats.items(), key=lambda x: x[1], reverse=True)[:20]),
            'computers': computers_stats,
            'analysis_completed': datetime.now().isoformat()
        }
        
        # Save statistics
        if output_file:
            stats_file = output_file.parent / f"{output_file.stem}_stats.json"
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, indent=2, fp=f)
            print(f"📊 Statistics saved to: {stats_file}")
        
        print(f"\n✅ Analysis Complete!")
        print(f"📊 Total Events Scanned: {events_count:,}")
        print(f"✅ Matched Filters: {matched_count:,}")
        print(f"\n📡 Channels Distribution:")
        for channel, count in sorted(channels_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  {channel}: {count:,} events")
        
        return stats


def process_timeline_analysis(xml_files: List[Path], output_name: str = None, 
                              filters: Dict = None, progress_callback=None):
    """Main function to process timeline analysis"""
    analyzer = TimelineAnalyzer()
    
    if output_name is None:
        output_name = f"timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    output_path = TIMELINE_DIR / f"{output_name}.csv"
    
    stats = analyzer.analyze_timeline(
        xml_files=xml_files,
        output_file=output_path,
        filters=filters,
        progress_callback=progress_callback
    )
    
    return {
        'timeline_path': str(output_path),
        'stats': stats
    }
