import React from 'react';
import axios from 'axios';

import { COUCHDB_AUTH, COUCHDB_DATABASE, COUCHDB_URL } from './couchdbConfig';

class Messages extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      data: [],
      loading: true,
      error: null
    };

    this.dbConfig = {
      url: COUCHDB_URL,
      database: COUCHDB_DATABASE,
      designDoc: '',
      view: ''
    };

    this.auth = COUCHDB_AUTH;
  }

  componentDidMount() {
    this.fetchData();
  }

  fetchData = async () => {
    try {
      this.setState({ loading: true, error: null });

      // Option 1: Fetch all documents in the database
      // const response = await axios.get(
      //   `${this.dbConfig.url}/${this.dbConfig.database}/_all_docs?include_docs=true`,
      //   { auth: this.auth }
      // );
      
      // Option 2: Query a specific view
      const response = await axios.get(
        // `${this.dbConfig.url}/${this.dbConfig.database}/${this.dbConfig.designDoc}/_view/${this.dbConfig.view}`,
        `${this.dbConfig.url}/${this.dbConfig.database}/_all_docs?include_docs=true`,
        { auth: this.auth }
      );

      // Extract the documents from the response
      const docs = response.data.rows.map(row => row.doc || row.value);
      const docsWithMedia = docs.filter((row) => row.raw.media?.document?.attributes[0]?.file_name ? true : false);
      console.log(docsWithMedia);
      this.setState({ data: docsWithMedia });
    } catch (error) {
      this.setState({ 
        error: error.message || 'Failed to fetch data from CouchDB',
        data: [] 
      });
    } finally {
      this.setState({ loading: false, showDownloadBtn: false });
    }
  };

  fetchStl = () => {
    let newData = this.state.data.filter((row) => row.raw.media?.document?.attributes[0]?.file_name.match(/\.stl$/g));
    this.setState({ data: newData, showDownloadBtn: true });
  }

  download = async (id: number, _id: string) => {
    const response = await axios.post(
      `http://localhost/telegram/download`, {id: id, _id: _id}
    );
    let row = this.state.data.filter((row) => row.raw.id == id)
    let data = this.state.data;
    data[data.indexOf(row[0])].uploaded = true;
    let savedUrl = /Saved to: \/app\/public(.[^\n]+)/g.exec(response.data)[1];
    data[data.indexOf(row[0])].savedUrl = savedUrl;
    this.setState({ data: data, });
  }

  render() {
    const { data, loading, error, showDownloadBtn } = this.state;

    const classObj = {
      'display-none': !showDownloadBtn,
    };
    
    // Convert object to className string
    const classesString = Object.keys(classObj)
      .filter(key => classObj[key]) // Keep only truthy values
      .join(' ');

    if (loading) {
      return <div>Loading data from CouchDB...</div>;
    }

    if (error) {
      return <div>Error: {error}</div>;
    }

    return (
      <div>
        <h2>CouchDB Data</h2>
        <button onClick={this.fetchData}>Refresh Data</button>
        <button onClick={this.fetchStl}>Fetch STL</button>
        {data.length === 0 ? (
          <p>No documents found in the database.</p>
        ) : (
          <ul>
            {data.map((doc) => (
              <li key={doc._id}>
                <pre>{doc.raw.media?.document?.attributes[0]?.file_name}</pre>
                <button className={classesString} onClick={() => this.download(doc.raw.id, doc._id)}>Download</button>
                {doc.uploaded && <div className='uploaded'>Uploaded</div>}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
}

export default Messages;